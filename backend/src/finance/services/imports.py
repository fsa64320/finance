"""Import de fichiers : aperçu sans rien écrire, puis validation en une seule transaction.

Le fichier est lu une fois, à l'aperçu. Les lignes lues restent en mémoire sous un jeton qui
expire ; la validation rejoue le dédoublonnage et les règles métier contre l'état courant de la
base, crée au besoin les actifs choisis par la personne, puis écrit tout ou rien (FR-016 à FR-020).
"""

import hashlib
import secrets
import time
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.entries import Entry
from finance.domain.enums import InstrumentKind
from finance.domain.enums import TransactionType as T
from finance.domain.fingerprint import LineFacts, fingerprint_lines, is_duplicate
from finance.domain.ledger import cash_effect
from finance.importers.base import (
    DetectedSettings,
    ImportFileError,
    ImportSettings,
    ParsedRow,
    RejectedRow,
)
from finance.importers.csv_generic import CsvImporter
from finance.services import import_mappings, instruments, loaders
from finance.services.errors import FieldError, NotFoundError, ValidationFailed
from finance.services.transactions import TransactionData, evaluate_transaction

MAX_FILE_BYTES = 5 * 1024 * 1024
PREVIEW_TTL_SECONDS = 30 * 60
PREVIEW_CAPACITY = 20
SAMPLE_SIZE = 10

_IMPORTER = CsvImporter()
_NEEDS_INSTRUMENT = frozenset({T.BUY, T.SELL, T.DIVIDEND, T.DISTRIBUTION})


class PreviewStore[V]:
    """Aperçus en attente de validation : en mémoire, bornés en nombre et en durée."""

    def __init__(
        self,
        *,
        ttl_seconds: float = PREVIEW_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        capacity: int = PREVIEW_CAPACITY,
    ) -> None:
        self._ttl, self._clock, self._capacity = ttl_seconds, clock, capacity
        self._items: OrderedDict[str, tuple[float, V]] = OrderedDict()

    def put(self, value: V) -> str:
        self._expire()
        token = secrets.token_urlsafe(16)
        self._items[token] = (self._clock() + self._ttl, value)
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)
        return token

    def get(self, token: str) -> V | None:
        self._expire()
        item = self._items.get(token)
        return None if item is None else item[1]

    def discard(self, token: str) -> None:
        self._items.pop(token, None)

    def _expire(self) -> None:
        now = self._clock()
        for token in [key for key, (deadline, _) in self._items.items() if deadline <= now]:
            del self._items[token]


@dataclass(frozen=True)
class PendingRow:
    row: ParsedRow
    fingerprint: str
    group: str | None  # clé de l'actif tel que le fichier le désigne ; vide hors actif


@dataclass(frozen=True)
class PreviewState:
    account_id: str
    file_name: str
    file_hash: str
    mapping_id: str | None
    settings: ImportSettings
    rows: list[PendingRow]
    rejected: list[RejectedRow]  # rejets de lecture


@dataclass(frozen=True)
class UnknownInstrument:
    key: str
    name: str
    isin: str | None
    rows: int


@dataclass(frozen=True)
class Resolution:
    key: str
    action: str  # create, link ou skip
    kind: InstrumentKind | None = None
    instrument_id: str | None = None


@dataclass(frozen=True)
class SampleRow:
    row: ParsedRow
    status: str  # new ou duplicate


@dataclass(frozen=True)
class PreviewResult:
    preview_id: str
    detected: DetectedSettings
    mapping_id: str | None
    columns: dict[str, str]
    rows_valid: int
    rows_duplicate: int
    rows_rejected: list[RejectedRow]
    unknown_instruments: list[UnknownInstrument]
    sample: list[SampleRow]


@dataclass(frozen=True)
class ImportOutcome:
    import_id: str
    rows_added: int
    rows_skipped: int
    rows_rejected: int
    instruments_created: int


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", " ".join(text.split()).casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _group(row: ParsedRow) -> str | None:
    if row.type not in _NEEDS_INSTRUMENT:
        return None
    if row.isin:
        return row.isin
    return f"name:{_fold(row.instrument_name or '')}"


def _account(session: Session, account_id: str) -> models.Account:
    account = session.get(models.Account, account_id)
    if account is None:
        raise ValidationFailed.single("account_id", "Compte introuvable.")
    return account


def _pending_rows(account_id: str, rows: Sequence[ParsedRow]) -> list[PendingRow]:
    facts = [
        LineFacts(
            trade_date=row.trade_date,
            type=row.type,
            instrument_key=_group(row) or "",
            quantity=row.quantity,
            unit_price=row.unit_price,
            amount=row.amount,
            fees=row.fees,
            label=row.label,
        )
        for row in rows
    ]
    prints = fingerprint_lines(account_id, facts)
    return [
        PendingRow(row=row, fingerprint=print_, group=_group(row))
        for row, print_ in zip(rows, prints, strict=True)
    ]


def _known_lines(session: Session, account_id: str) -> tuple[set[str], set[str]]:
    version, txn = models.TransactionVersion, models.Transaction
    rows = session.execute(
        sa.select(version.external_id, version.line_fingerprint)
        .join(txn, txn.id == version.transaction_id)
        .where(txn.account_id == account_id)
        .where(sa.or_(version.external_id.is_not(None), version.line_fingerprint.is_not(None)))
    )
    external_ids: set[str] = set()
    fingerprints: set[str] = set()
    for external_id, fingerprint in rows:
        if external_id is not None:
            external_ids.add(external_id)
        if fingerprint is not None:
            fingerprints.add(fingerprint)
    return external_ids, fingerprints


def _known_instruments(session: Session) -> dict[str, str]:
    """Actifs de l'application, par ISIN puis par nom normalisé (`name:…`)."""
    known: dict[str, str] = {}
    for item in session.scalars(sa.select(models.Instrument).order_by(models.Instrument.name)):
        if item.isin:
            known[item.isin] = item.id
        known.setdefault(f"name:{_fold(item.name)}", item.id)
    return known


def _unknown(pending: Sequence[PendingRow], known: dict[str, str]) -> list[UnknownInstrument]:
    found: dict[str, UnknownInstrument] = {}
    for item in pending:
        if item.group is None or item.group in known:
            continue
        current = found.get(item.group)
        name = item.row.instrument_name or item.row.isin or item.group
        found[item.group] = UnknownInstrument(
            key=item.group,
            name=current.name if current else name,
            isin=item.row.isin or (current.isin if current else None),
            rows=(current.rows if current else 0) + 1,
        )
    return list(found.values())


@dataclass
class Evaluation:
    new: list[tuple[PendingRow, TransactionData]] = field(default_factory=list)
    duplicates: list[PendingRow] = field(default_factory=list)
    skipped: list[PendingRow] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)


def _evaluate_rows(
    session: Session,
    account: models.Account,
    pending: Sequence[PendingRow],
    instrument_ids: dict[str, str | None],
) -> Evaluation:
    """Doublons puis règles métier, dans l'ordre chronologique, avec un seul chargement du compte.

    `instrument_ids` donne l'actif de chaque clé ; `None` signifie « ignorer les lignes ».
    """
    known_external, known_prints = _known_lines(session, account.id)
    entries = loaders.load_entries(session, account_ids=[account.id])
    outcome = Evaluation()
    now = datetime.now(UTC)
    for item in sorted(pending, key=lambda p: (p.row.trade_date, p.row.line)):
        row = item.row
        instrument_id: str | None = None
        if item.group is not None:
            if item.group not in instrument_ids:
                outcome.rejected.append(RejectedRow(row.line, "Actif non résolu."))
                continue
            instrument_id = instrument_ids[item.group]
            if instrument_id is None:
                outcome.skipped.append(item)
                continue
        if is_duplicate(
            row.external_id,
            item.fingerprint,
            known_external_ids=known_external,
            known_fingerprints=known_prints,
        ):
            outcome.duplicates.append(item)
            continue
        if row.external_id is not None:
            known_external.add(row.external_id)
        is_trade = row.type in (T.BUY, T.SELL)
        data = TransactionData(
            account_id=account.id,
            type=row.type,
            trade_date=row.trade_date,
            currency=account.currency,
            instrument_id=instrument_id,
            quantity=row.quantity if is_trade else None,
            unit_price=row.unit_price if is_trade else None,
            amount=None if is_trade else row.amount,
            fees=row.fees,
            label=row.label,
        )
        try:
            cash, _ = evaluate_transaction(account, entries, data, with_cash_warning=False)
        except ValidationFailed as failure:
            reason = " ; ".join(detail.message for detail in failure.details)
            outcome.rejected.append(RejectedRow(row.line, reason))
            continue
        entries.append(_synthetic(item, data, cash, now))
        outcome.new.append((item, data))
    outcome.rejected.sort(key=lambda rejected: rejected.line)
    return outcome


def _synthetic(item: PendingRow, data: TransactionData, cash: Decimal, now: datetime) -> Entry:
    return Entry(
        transaction_id=f"import-{item.row.line}",
        version=1,
        account_id=data.account_id,
        type=data.type,
        trade_date=data.trade_date,
        cash_amount=cash,
        currency=data.currency,
        created_at=now,
        instrument_id=data.instrument_id,
        quantity=data.quantity,
        unit_price=data.unit_price,
        fees=data.fees,
        label=data.label,
    )


def _file_error(failure: ImportFileError) -> ValidationFailed:
    return ValidationFailed.single(failure.field, str(failure))


def preview(
    session: Session,
    store: PreviewStore[PreviewState],
    *,
    account_id: str,
    file_name: str,
    content: bytes,
    mapping_id: str | None = None,
    delimiter: str | None = None,
    encoding: str | None = None,
    date_format: str | None = None,
    decimal_separator: str | None = None,
    columns: dict[str, str] | None = None,
) -> PreviewResult:
    account = _account(session, account_id)
    if len(content) > MAX_FILE_BYTES:
        raise ValidationFailed.single(
            "file",
            f"Le fichier est trop volumineux (maximum {MAX_FILE_BYTES // (1024 * 1024)} Mio).",
        )
    if delimiter is not None and len(delimiter) != 1:
        raise ValidationFailed.single("delimiter", "Le séparateur est un seul caractère.")
    try:
        detected = _IMPORTER.detect(content)
    except ImportFileError as failure:
        raise _file_error(failure) from failure

    mapping: models.ImportMapping | None = None
    if mapping_id is not None:
        try:
            mapping = import_mappings.get_mapping(session, mapping_id)
        except NotFoundError:
            raise ValidationFailed.single("mapping_id", "Paramétrage introuvable.") from None
    elif not columns:
        mapping = import_mappings.suggest_mapping(session, detected.headers)
    applied = columns or (dict(mapping.columns) if mapping else {})

    settings = ImportSettings(
        delimiter=delimiter or (mapping.delimiter if mapping else detected.delimiter),
        encoding=encoding or (mapping.encoding if mapping else detected.encoding),
        date_format=date_format or (mapping.date_format if mapping else detected.date_format),
        decimal_separator=decimal_separator
        or (mapping.decimal_separator if mapping else detected.decimal_separator),
        columns=applied,
    )
    # Les réglages explicites ou enregistrés ont pu changer la lecture de l'en-tête.
    shown = (
        detected
        if not applied
        else replace(
            detected,
            delimiter=settings.delimiter,
            encoding=settings.encoding,
            date_format=settings.date_format,
            decimal_separator=settings.decimal_separator,
        )
    )

    parsed_rows: list[ParsedRow] = []
    read_rejects: list[RejectedRow] = []
    if applied:
        try:
            parsed = _IMPORTER.parse(content, settings)
        except ImportFileError as failure:
            raise _file_error(failure) from failure
        parsed_rows, read_rejects = parsed.rows, parsed.rejected

    pending = _pending_rows(account.id, parsed_rows)
    known = _known_instruments(session)
    unknown = _unknown(pending, known)
    # Les actifs inconnus sont évalués sous un identifiant provisoire : rien n'est créé ici.
    ids: dict[str, str | None] = {
        item.group: known.get(item.group, f"pending:{item.group}")
        for item in pending
        if item.group is not None
    }
    evaluation = _evaluate_rows(session, account, pending, ids)

    state = PreviewState(
        account_id=account.id,
        file_name=file_name,
        file_hash=hashlib.sha256(content).hexdigest(),
        mapping_id=mapping.id if mapping else None,
        settings=settings,
        rows=pending,
        rejected=read_rejects,
    )
    new_lines = {item.row.line for item, _ in evaluation.new}
    sample = [
        SampleRow(row=item.row, status="new" if item.row.line in new_lines else "duplicate")
        for item in pending
        if item.row.line in new_lines or item in evaluation.duplicates
    ][:SAMPLE_SIZE]
    return PreviewResult(
        preview_id=store.put(state),
        detected=shown,
        mapping_id=state.mapping_id,
        columns=applied,
        rows_valid=len(evaluation.new),
        rows_duplicate=len(evaluation.duplicates),
        rows_rejected=sorted([*read_rejects, *evaluation.rejected], key=lambda r: r.line),
        unknown_instruments=unknown,
        sample=sample,
    )


def _resolve(
    session: Session,
    unknown: list[UnknownInstrument],
    resolutions: Sequence[Resolution],
) -> dict[str, Resolution]:
    by_key = {resolution.key: resolution for resolution in resolutions}
    problems: list[FieldError] = []
    for item in unknown:
        resolution = by_key.get(item.key)
        if resolution is None:
            problems.append(
                FieldError(
                    "instrument_resolutions",
                    f"Choisissez quoi faire de l'actif « {item.name} » (créer, lier, ignorer).",
                )
            )
        elif resolution.action == "create" and resolution.kind is None:
            problems.append(
                FieldError(
                    "instrument_resolutions",
                    f"Indiquez le type de l'actif « {item.name} » à créer.",
                )
            )
        elif resolution.action == "link" and (
            resolution.instrument_id is None
            or session.get(models.Instrument, resolution.instrument_id) is None
        ):
            problems.append(
                FieldError(
                    "instrument_resolutions",
                    f"Actif introuvable pour le rattachement de « {item.name} ».",
                )
            )
        elif resolution.action not in ("create", "link", "skip"):
            problems.append(
                FieldError("instrument_resolutions", f"Action inconnue pour « {item.name} ».")
            )
    if problems:
        raise ValidationFailed(problems)
    return by_key


def commit(
    session: Session,
    store: PreviewStore[PreviewState],
    *,
    preview_id: str,
    confirm_rejected: bool,
    resolutions: Sequence[Resolution] = (),
    save_mapping_as: str | None = None,
) -> ImportOutcome:
    state = store.get(preview_id)
    if state is None:
        raise NotFoundError("Aperçu", preview_id)
    account = _account(session, state.account_id)
    if save_mapping_as is not None:
        import_mappings.ensure_name_free(session, save_mapping_as)

    known = _known_instruments(session)
    unknown = _unknown(state.rows, known)
    chosen = _resolve(session, unknown, resolutions)
    ids: dict[str, str | None] = {
        item.group: known[item.group] for item in state.rows if item.group in known
    }
    for item in unknown:
        resolution = chosen[item.key]
        if resolution.action == "skip":
            ids[item.key] = None
        elif resolution.action == "link":
            ids[item.key] = resolution.instrument_id
        else:
            ids[item.key] = f"pending:{item.key}"
    evaluation = _evaluate_rows(session, account, state.rows, ids)

    rejected = len(state.rejected) + len(evaluation.rejected)
    if rejected and not confirm_rejected:
        raise ValidationFailed.single(
            "confirm_rejected",
            f"{rejected} ligne(s) sont invalides : confirmez l'import des autres lignes "
            "ou corrigez le fichier.",
        )

    created: dict[str, str] = {}
    for item in unknown:
        resolution = chosen[item.key]
        if resolution.action == "create" and resolution.kind is not None:
            made = instruments.create_instrument(
                session,
                kind=resolution.kind,
                name=item.name,
                currency=account.currency,
                isin=item.isin,
            )
            created[f"pending:{item.key}"] = made.id

    mapping_id = state.mapping_id
    if save_mapping_as is not None:
        saved = import_mappings.create_mapping(
            session,
            import_mappings.MappingData(
                name=save_mapping_as,
                delimiter=state.settings.delimiter,
                encoding=state.settings.encoding,
                date_format=state.settings.date_format,
                decimal_separator=state.settings.decimal_separator,
                columns=dict(state.settings.columns),
            ),
        )
        mapping_id = saved.id

    skipped = len(evaluation.duplicates) + len(evaluation.skipped)
    batch = models.ImportBatch(
        account_id=account.id,
        file_name=state.file_name,
        file_hash=state.file_hash,
        mapping_id=mapping_id,
        rows_added=len(evaluation.new),
        rows_skipped=skipped,
        rows_rejected=rejected,
    )
    session.add(batch)
    session.flush()

    transactions = [models.Transaction(account_id=account.id) for _ in evaluation.new]
    session.add_all(transactions)
    session.flush()
    versions: list[models.TransactionVersion] = []
    for transaction, (line, data) in zip(transactions, evaluation.new, strict=True):
        instrument_id = created.get(data.instrument_id or "", data.instrument_id)
        versions.append(
            models.TransactionVersion(
                transaction_id=transaction.id,
                version=1,
                voided=False,
                type=data.type,
                trade_date=data.trade_date,
                instrument_id=instrument_id,
                quantity=data.quantity,
                unit_price=data.unit_price,
                fees=data.fees,
                cash_amount=cash_effect(
                    data.type,
                    amount=data.amount,
                    quantity=data.quantity,
                    unit_price=data.unit_price,
                    fees=data.fees,
                ),
                currency=data.currency,
                label=data.label,
                external_id=line.row.external_id,
                line_fingerprint=line.fingerprint,
                import_id=batch.id,
            )
        )
    session.add_all(versions)
    session.flush()
    store.discard(preview_id)
    return ImportOutcome(
        import_id=batch.id,
        rows_added=len(versions),
        rows_skipped=skipped,
        rows_rejected=rejected,
        instruments_created=len(created),
    )
