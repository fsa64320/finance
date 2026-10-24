"""Types de colonnes : texte décimal exact (principe III) et horodatage UTC."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Dialect, String
from sqlalchemy.types import TypeDecorator

_DECIMAL_TEXT = re.compile(r"-?\d+(\.\d+)?")


def canonical_decimal_text(value: object) -> str:
    """Texte décimal canonique : point, sans exposant, sans zéro inutile (1.50 → 1.5, -0 → 0)."""
    if isinstance(value, bool | float):
        raise TypeError(f"un montant décimal n'accepte pas {type(value).__name__}")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, str):
        if not _DECIMAL_TEXT.fullmatch(value):
            raise ValueError(f"valeur décimale invalide : {value!r}")
        number = Decimal(value)
    else:
        raise TypeError(f"un montant décimal n'accepte pas {type(value).__name__}")
    if not number.is_finite():
        raise ValueError(f"valeur décimale non finie : {value!r}")
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


class DecimalText(TypeDecorator[Decimal]):
    """Décimal stocké en texte canonique : SQLite n'a pas de type décimal exact.

    Les comparaisons et sommes se font en Python, jamais en SQL (qui passerait par un flottant).
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        return None if value is None else canonical_decimal_text(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Decimal | None:
        return None if value is None else Decimal(value)


class UtcDateTime(TypeDecorator[datetime]):
    """Horodatage toujours en UTC : refuse une date sans fuseau, rend une date avec fuseau."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("horodatage sans fuseau horaire refusé")
        naive: datetime = value.astimezone(UTC).replace(tzinfo=None)
        return naive

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        aware: datetime = value.replace(tzinfo=UTC)
        return aware
