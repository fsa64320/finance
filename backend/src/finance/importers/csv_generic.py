"""Importeur CSV générique : détection des réglages, puis lecture selon une correspondance."""

import codecs
import csv
import io
import re
import unicodedata
from datetime import datetime
from decimal import Decimal

from charset_normalizer import from_bytes

from finance.domain.enums import TransactionType as T
from finance.domain.isin import is_valid_isin, normalize_isin
from finance.importers.base import (
    DetectedSettings,
    ImportFileError,
    ImportSettings,
    ParsedRow,
    ParseResult,
    RejectedRow,
)

DELIMITERS = ";,\t|"
DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y")
SAMPLE_ROWS = 200
FIELDS = (
    "trade_date",
    "type",
    "instrument_name",
    "isin",
    "quantity",
    "unit_price",
    "amount",
    "fees",
    "label",
    "external_id",
)

_NUMERIC_LOOKING = re.compile(r"[+-]?\d[\d \u00a0\u202f.,]*")
_PLAIN_NUMBER = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)")
_SPACES = re.compile(r"[ \u00a0\u202f]")

# Vocabulaire des types, sans accents ni majuscules.
_TYPE_WORDS: dict[str, T] = {
    "achat": T.BUY,
    "buy": T.BUY,
    "vente": T.SELL,
    "sell": T.SELL,
    "dividende": T.DIVIDEND,
    "dividendes": T.DIVIDEND,
    "dividend": T.DIVIDEND,
    "distribution": T.DISTRIBUTION,
    "interet": T.INTEREST,
    "interets": T.INTEREST,
    "interest": T.INTEREST,
    "frais": T.FEE,
    "fee": T.FEE,
    "fees": T.FEE,
    "retrait": T.WITHDRAWAL,
    "withdrawal": T.WITHDRAWAL,
    "versement": T.DEPOSIT,
    "depot": T.DEPOSIT,
    "deposit": T.DEPOSIT,
    "abondement": T.EMPLOYER_MATCH,
    "employer_match": T.EMPLOYER_MATCH,
}
_NEEDS_INSTRUMENT = frozenset({T.BUY, T.SELL, T.DIVIDEND, T.DISTRIBUTION})
_TRADES = frozenset({T.BUY, T.SELL})


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.strip().casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _detect_encoding(content: bytes) -> str:
    if content.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        best = from_bytes(content).best()
        if best is not None and best.encoding.startswith(("utf_16", "utf_32")):
            return best.encoding.replace("_", "-")
        return "windows-1252"
    return "utf-8"


def _decode(content: bytes, encoding: str, *, strict: bool) -> str:
    try:
        return content.decode(encoding, errors="strict" if strict else "replace")
    except (LookupError, UnicodeDecodeError):
        raise ImportFileError(
            f"Le fichier n'est pas lisible avec l'encodage « {encoding} » : changez l'encodage."
        ) from None


def _require_content(content: bytes) -> None:
    if not content.strip():
        raise ImportFileError("Le fichier est vide.")


def _detect_delimiter(text: str) -> str:
    header = next((line for line in text.splitlines() if line.strip()), "")
    best, best_count = ";", 1
    for candidate in DELIMITERS:
        count = len(next(csv.reader([header], delimiter=candidate), []))
        if count > best_count:
            best, best_count = candidate, count
    return best


def _detect_date_format(rows: list[list[str]]) -> str:
    width = max((len(row) for row in rows), default=0)
    for fmt in DATE_FORMATS:
        for index in range(width):
            values = [row[index].strip() for row in rows if index < len(row) and row[index].strip()]
            if values and all(_parses_as_date(value, fmt) for value in values):
                return fmt
    return DATE_FORMATS[0]


def _parses_as_date(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
    except ValueError:
        return False
    return True


def _detect_decimal_separator(rows: list[list[str]]) -> str:
    votes = {",": 0, ".": 0}
    for row in rows:
        for cell in row:
            value = cell.strip()
            if not _NUMERIC_LOOKING.fullmatch(value):
                continue
            last = max(value.rfind(","), value.rfind("."))
            if last < 0:
                continue
            separator = value[last]
            digits_after = len(value) - last - 1
            other = "." if separator == "," else ","
            if other in value or (value.count(separator) == 1 and digits_after != 3):
                votes[separator] += 1
    return "." if votes["."] > votes[","] else ","


def detect_settings(content: bytes) -> DetectedSettings:
    _require_content(content)
    encoding = _detect_encoding(content)
    text = _decode(content, encoding, strict=False)
    delimiter = _detect_delimiter(text)
    records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
    records = [row for row in records if any(cell.strip() for cell in row)]
    headers = [cell.strip() for cell in records[0]] if records else []
    body = records[1 : 1 + SAMPLE_ROWS]
    return DetectedSettings(
        delimiter=delimiter,
        encoding=encoding,
        date_format=_detect_date_format(body),
        decimal_separator=_detect_decimal_separator(body),
        headers=headers,
    )


class _BadValue(ValueError):
    pass


def _number(raw: str, column: str, decimal_separator: str) -> Decimal:
    cleaned = _SPACES.sub("", raw.strip()).replace("€", "")
    if decimal_separator == ",":
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    if not _PLAIN_NUMBER.fullmatch(cleaned):
        raise _BadValue(f"Nombre illisible dans « {column} » : « {raw.strip()} »")
    return Decimal(cleaned)


class _Row:
    """Accès aux cellules d'une ligne par donnée d'opération."""

    def __init__(self, cells: list[str], indexes: dict[str, int], columns: dict[str, str]):
        self._cells, self._indexes, self._columns = cells, indexes, columns

    def text(self, field_name: str) -> str | None:
        index = self._indexes.get(field_name)
        if index is None or index >= len(self._cells):
            return None
        value = self._cells[index].strip()
        return value or None

    def column(self, field_name: str) -> str:
        return self._columns[field_name]


def _parse_row(line: int, row: _Row, settings: ImportSettings) -> ParsedRow:
    raw_date = row.text("trade_date")
    if raw_date is None:
        raise _BadValue("Date manquante")
    try:
        trade_date = datetime.strptime(raw_date, settings.date_format).date()
    except ValueError:
        raise _BadValue(f"Date illisible : « {raw_date} »") from None

    raw_type = row.text("type")
    if raw_type is None:
        raise _BadValue("Type d'opération manquant")
    kind = _TYPE_WORDS.get(_fold(raw_type))
    if kind is None:
        raise _BadValue(f"Type d'opération inconnu : « {raw_type} »")

    numbers: dict[str, Decimal | None] = {}
    for field_name in ("quantity", "unit_price", "amount", "fees"):
        raw = row.text(field_name)
        numbers[field_name] = (
            None
            if raw is None
            else abs(_number(raw, row.column(field_name), settings.decimal_separator))
        )

    name: str | None = row.text("instrument_name")
    raw_isin = row.text("isin")
    isin: str | None = None
    if raw_isin is not None:
        isin = normalize_isin(raw_isin)
        if not is_valid_isin(isin):
            raise _BadValue(f"Code ISIN invalide : « {raw_isin} »")

    if kind in _NEEDS_INSTRUMENT:
        if name is None and isin is None:
            raise _BadValue("Actif manquant (nom ou code ISIN)")
    else:
        name, isin = None, None
    if kind in _TRADES:
        if numbers["quantity"] is None:
            raise _BadValue("Quantité manquante")
        if numbers["unit_price"] is None:
            raise _BadValue("Prix manquant")
    elif numbers["amount"] is None:
        raise _BadValue("Montant manquant")

    return ParsedRow(
        line=line,
        trade_date=trade_date,
        type=kind,
        instrument_name=name,
        isin=isin,
        quantity=numbers["quantity"],
        unit_price=numbers["unit_price"],
        amount=numbers["amount"],
        fees=numbers["fees"] or Decimal(0),
        label=row.text("label"),
        external_id=row.text("external_id"),
    )


def parse_csv(content: bytes, settings: ImportSettings) -> ParseResult:
    _require_content(content)
    columns = {key: value for key, value in settings.columns.items() if key in FIELDS and value}
    if "trade_date" not in columns or "type" not in columns:
        raise ImportFileError(
            "La correspondance doit indiquer la colonne de la date et celle du type d'opération."
        )
    text = _decode(content, settings.encoding, strict=True)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=settings.delimiter)
    header = next((row for row in reader if any(cell.strip() for cell in row)), [])
    positions = {cell.strip(): index for index, cell in enumerate(header)}
    indexes: dict[str, int] = {}
    for field_name, column in columns.items():
        if column.strip() not in positions:
            raise ImportFileError(f"Colonne introuvable dans le fichier : « {column} »")
        indexes[field_name] = positions[column.strip()]

    rows: list[ParsedRow] = []
    rejected: list[RejectedRow] = []
    for cells in reader:
        if not any(cell.strip() for cell in cells):
            continue
        line = reader.line_num
        try:
            rows.append(_parse_row(line, _Row(cells, indexes, columns), settings))
        except _BadValue as problem:
            rejected.append(RejectedRow(line=line, reason=str(problem)))
    return ParseResult(rows=rows, rejected=rejected)


class CsvImporter:
    def detect(self, content: bytes) -> DetectedSettings:
        return detect_settings(content)

    def parse(self, content: bytes, settings: ImportSettings) -> ParseResult:
        return parse_csv(content, settings)
