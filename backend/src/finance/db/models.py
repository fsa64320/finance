"""Modèle de données (data-model.md).

Journal en ajout seul : `transaction`, `transaction_version`, `transfer_group`, `price`,
`declared_balance`, `rate` et `import_batch` ne reçoivent ni UPDATE ni DELETE (voir append_only.py).
Aucune valeur dérivée n'est stockée : les montants se recalculent depuis ces tables.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from finance.db.types import DecimalText, UtcDateTime
from finance.domain.enums import (
    AccountType,
    InstrumentKind,
    PriceKind,
    PriceMode,
    PriceSource,
    RateKind,
    RateSource,
    TransactionType,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_class: type, name: str) -> Enum:
    """Énumération stockée en texte avec une contrainte CHECK sur les valeurs autorisées."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (
        CheckConstraint("closed_on IS NULL OR closed_on >= opened_on", name="closed_after_opened"),
        # Le nom d'un compte est unique parmi les comptes ouverts : une clôture libère le nom.
        Index(
            "uq_account_open_name",
            "name",
            unique=True,
            sqlite_where=text("closed_on IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[AccountType] = mapped_column(enum_column(AccountType, "account_type"))
    name: Mapped[str] = mapped_column(String(200))
    institution: Mapped[str | None] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3))
    opened_on: Mapped[date] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date)
    # Paramètres propres au type : deposit_cap (PEA, Livret A), lock_years (PEE).
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class Instrument(Base):
    __tablename__ = "instrument"
    __table_args__ = (CheckConstraint("isin IS NULL OR length(isin) = 12", name="isin_length"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[InstrumentKind] = mapped_column(enum_column(InstrumentKind, "instrument_kind"))
    name: Mapped[str] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(12), unique=True)
    currency: Mapped[str] = mapped_column(String(3))
    price_ticker: Mapped[str | None] = mapped_column(String(50))
    price_mode: Mapped[PriceMode] = mapped_column(
        enum_column(PriceMode, "price_mode"), default=PriceMode.MANUAL
    )


class Transaction(Base):
    """Identité stable d'une opération ; son contenu vit dans `transaction_version`."""

    __tablename__ = "transaction"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class TransferGroup(Base):
    """Relie les deux jambes d'un virement entre comptes (sortie et entrée)."""

    __tablename__ = "transfer_group"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class ImportMapping(Base):
    __tablename__ = "import_mapping"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    delimiter: Mapped[str] = mapped_column(String(1))
    encoding: Mapped[str] = mapped_column(String(50))
    date_format: Mapped[str] = mapped_column(String(50))
    decimal_separator: Mapped[str] = mapped_column(String(1))
    columns: Mapped[dict[str, Any]] = mapped_column(JSON)


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(500))
    file_hash: Mapped[str] = mapped_column(String(128), index=True)
    mapping_id: Mapped[str | None] = mapped_column(ForeignKey("import_mapping.id"))
    rows_added: Mapped[int]
    rows_skipped: Mapped[int]
    rows_rejected: Mapped[int]
    imported_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class TransactionVersion(Base):
    """Une ligne par version d'une opération ; la dernière version fait foi."""

    __tablename__ = "transaction_version"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_transaction_version_trade_date", "trade_date"),
    )

    transaction_id: Mapped[str] = mapped_column(ForeignKey("transaction.id"), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    voided: Mapped[bool] = mapped_column(default=False)
    type: Mapped[TransactionType] = mapped_column(enum_column(TransactionType, "transaction_type"))
    trade_date: Mapped[date] = mapped_column(Date)
    instrument_id: Mapped[str | None] = mapped_column(ForeignKey("instrument.id"), index=True)
    quantity: Mapped[Decimal | None] = mapped_column(DecimalText)
    unit_price: Mapped[Decimal | None] = mapped_column(DecimalText)
    fees: Mapped[Decimal] = mapped_column(DecimalText, default=Decimal(0))
    # Effet signé sur la trésorerie du compte, calculé à la saisie selon le type et conservé.
    cash_amount: Mapped[Decimal] = mapped_column(DecimalText)
    currency: Mapped[str] = mapped_column(String(3))
    unlock_date: Mapped[date | None] = mapped_column(Date)
    transfer_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("transfer_group.id"), index=True
    )
    label: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    line_fingerprint: Mapped[str | None] = mapped_column(String(128), index=True)
    import_id: Mapped[str | None] = mapped_column(ForeignKey("import_batch.id"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class Price(Base):
    __tablename__ = "price"
    __table_args__ = (Index("ix_price_instrument_date", "instrument_id", "price_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument.id"))
    price_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[PriceKind] = mapped_column(enum_column(PriceKind, "price_kind"))
    value: Mapped[Decimal] = mapped_column(DecimalText)
    currency: Mapped[str] = mapped_column(String(3))
    source: Mapped[PriceSource] = mapped_column(enum_column(PriceSource, "price_source"))
    # Départage deux saisies à la même date : la plus récente fait foi.
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class DeclaredBalance(Base):
    __tablename__ = "declared_balance"
    __table_args__ = (
        Index("ix_declared_balance_account_date", "account_id", "instrument_id", "balance_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("account.id"))
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instrument.id"))
    balance_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(DecimalText)
    currency: Mapped[str] = mapped_column(String(3))
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class Rate(Base):
    __tablename__ = "rate"
    __table_args__ = (Index("ix_rate_kind_pair_from", "kind", "base", "quote", "effective_from"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[RateKind] = mapped_column(enum_column(RateKind, "rate_kind"))
    base: Mapped[str | None] = mapped_column(String(3))
    quote: Mapped[str | None] = mapped_column(String(3))
    effective_from: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(DecimalText)
    source: Mapped[RateSource] = mapped_column(enum_column(RateSource, "rate_source"))
    # Ajout par rapport à data-model.md : le journal est en ajout seul, donc une correction de
    # taux insère une ligne et la plus récente à une même date fait foi.
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class Setting(Base):
    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
