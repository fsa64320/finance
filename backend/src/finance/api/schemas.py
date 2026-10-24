"""Schémas de l'API. Les montants circulent en chaînes décimales, jamais en nombres JSON."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, WithJsonSchema

from finance.db.types import canonical_decimal_text
from finance.domain.enums import AccountType, InstrumentKind, PriceKind


def _parse_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(canonical_decimal_text(value))
    raise ValueError('un montant est une chaîne décimale, par exemple "90.199"')


DecimalStr = Annotated[
    Decimal,
    BeforeValidator(_parse_decimal),
    PlainSerializer(canonical_decimal_text, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "pattern": r"^-?[0-9]+(\.[0-9]+)?$"}),
]

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class ApiTransactionType(StrEnum):
    """Types saisissables directement ; les virements passent par /transfers."""

    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    DISTRIBUTION = "DISTRIBUTION"
    INTEREST = "INTEREST"
    FEE = "FEE"
    EMPLOYER_MATCH = "EMPLOYER_MATCH"


class Strict(BaseModel):
    """Corps de requête : les champs inconnus sont refusés."""

    model_config = ConfigDict(extra="forbid")


class PasswordRequest(BaseModel):
    password: str = Field(min_length=12, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


class UnlockRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class AuthStatus(BaseModel):
    state: Literal["uninitialized", "locked", "unlocked"]


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None


class AccountInput(Strict):
    type: AccountType
    name: str = Field(min_length=1)
    institution: str | None = None
    currency: CurrencyCode | None = None
    opened_on: date
    settings: dict[str, Any] | None = None


class AccountPatch(Strict):
    name: str | None = None
    institution: str | None = None
    closed_on: date | None = None
    settings: dict[str, Any] | None = None


class InstrumentInput(Strict):
    kind: InstrumentKind
    name: str = Field(min_length=1)
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    currency: CurrencyCode
    price_ticker: str | None = None
    price_mode: Literal["AUTO", "MANUAL"] | None = None


class InstrumentPatch(Strict):
    name: str | None = None
    price_ticker: str | None = None
    price_mode: Literal["AUTO", "MANUAL"] | None = None


class TransactionInput(Strict):
    account_id: UUID
    type: ApiTransactionType
    trade_date: date
    instrument_id: UUID | None = None
    quantity: DecimalStr | None = None
    unit_price: DecimalStr | None = None
    amount: DecimalStr | None = None
    fees: DecimalStr | None = None
    currency: CurrencyCode
    unlock_date: date | None = None
    label: str | None = None


class TransferInput(Strict):
    from_account_id: UUID
    to_account_id: UUID
    trade_date: date
    amount: DecimalStr
    currency: CurrencyCode
    label: str | None = None


class DeclaredBalanceInput(Strict):
    account_id: UUID
    instrument_id: UUID
    balance_date: date
    amount: DecimalStr
    currency: CurrencyCode


class ImportMappingInput(Strict):
    name: str
    delimiter: str = Field(max_length=1)
    encoding: str
    date_format: str
    decimal_separator: Literal[",", "."]
    columns: dict[str, str]


class InstrumentResolutionInput(Strict):
    key: str
    action: Literal["create", "link", "skip"]
    kind: InstrumentKind | None = None
    instrument_id: UUID | None = None


class ImportCommitInput(Strict):
    preview_id: str
    confirm_rejected: bool
    instrument_resolutions: list[InstrumentResolutionInput] | None = None
    save_mapping_as: str | None = None


class PriceInput(Strict):
    instrument_id: UUID
    price_date: date
    kind: PriceKind
    value: DecimalStr
    currency: CurrencyCode


class LivretARateInput(Strict):
    effective_from: date
    value: DecimalStr


class SettingsPatch(Strict):
    reference_currency: str | None = None
    auto_fetch_prices: bool | None = None
    export_reminder_days: int | None = Field(default=None, ge=0)
