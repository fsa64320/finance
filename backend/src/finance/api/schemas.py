"""Schémas de l'API. Les montants circulent en chaînes décimales, jamais en nombres JSON."""

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer

from finance.db.types import canonical_decimal_text


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
]


class PasswordRequest(BaseModel):
    password: str = Field(min_length=12, max_length=128)


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
