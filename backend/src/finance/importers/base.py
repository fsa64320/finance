"""Interface commune des importeurs : un fichier entre, des lignes normalisées sortent.

Un importeur ne touche jamais à la base : il lit, normalise et signale les lignes rejetées. Les
décisions (doublons, actifs inconnus, écriture) appartiennent à `services/imports.py`.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from finance.domain.enums import TransactionType


class ImportFileError(ValueError):
    """Le fichier entier est inutilisable (vide, mal encodé, colonne introuvable…)."""


@dataclass(frozen=True)
class ImportSettings:
    delimiter: str
    encoding: str
    date_format: str
    decimal_separator: str
    # Donnée d'opération → nom de la colonne du fichier.
    columns: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DetectedSettings:
    delimiter: str
    encoding: str
    date_format: str
    decimal_separator: str
    headers: list[str]


@dataclass(frozen=True)
class ParsedRow:
    line: int
    trade_date: date
    type: TransactionType
    instrument_name: str | None = None
    isin: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    fees: Decimal = Decimal(0)
    label: str | None = None
    external_id: str | None = None


@dataclass(frozen=True)
class RejectedRow:
    line: int
    reason: str


@dataclass(frozen=True)
class ParseResult:
    rows: list[ParsedRow]
    rejected: list[RejectedRow]


class Importer(Protocol):
    def detect(self, content: bytes) -> DetectedSettings: ...

    def parse(self, content: bytes, settings: ImportSettings) -> ParseResult: ...
