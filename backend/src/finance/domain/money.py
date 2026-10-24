"""Montants avec leur devise (principe III).

Un montant est un `Decimal` exact : jamais de flottant. Il garde sa devise d'origine et n'est
arrondi qu'à l'affichage, en arrondissant la moitié vers l'extérieur de zéro (ROUND_HALF_UP).
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_CURRENCY = re.compile(r"[A-Z]{3}")


class CurrencyMismatchError(ValueError):
    """Opération entre deux devises différentes, sans conversion."""


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        amount = self.amount
        if isinstance(amount, bool) or not isinstance(amount, Decimal | int):
            raise TypeError(f"un montant est un Decimal, reçu {type(amount).__name__}")
        exact = Decimal(amount)
        if not exact.is_finite():
            raise ValueError("un montant doit être un décimal fini")
        object.__setattr__(self, "amount", exact)
        if not _CURRENCY.fullmatch(self.currency):
            raise ValueError(f"devise invalide : {self.currency!r} (trois lettres majuscules)")

    def _same_currency(self, other: "Money") -> None:
        if other.currency != self.currency:
            raise CurrencyMismatchError(
                f"{self.currency} et {other.currency} ne s'additionnent pas"
            )

    def __add__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: object) -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        self._same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __mul__(self, factor: object) -> "Money":
        if isinstance(factor, bool) or not isinstance(factor, Decimal | int):
            return NotImplemented
        return Money(self.amount * Decimal(factor), self.currency)

    def to_display(self, places: int = 2) -> Decimal:
        """Montant arrondi pour l'affichage ; la valeur exacte n'est pas modifiée."""
        return self.amount.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
