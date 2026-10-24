"""Conversion de devises au taux de la date de valorisation (FR-025).

Un taux est publié « 1 `base` = `value` `quote` » (la BCE publie contre l'euro). Les jours sans
publication reprennent le dernier taux connu. Deux devises étrangères passent par l'euro. Les
montants convertis sont arrondis à 10 décimales, très en deçà du centime affiché : cela garde les
sommes exactes quel que soit l'ordre d'addition.
"""

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext

PIVOT = "EUR"
FX_STALE_AFTER_DAYS = 7  # week-end prolongé et jours fériés compris
PRECISION = 50
_SCALE = Decimal("1e-10")


@dataclass(frozen=True)
class FxRateRow:
    base: str
    quote: str
    effective_from: date
    value: Decimal
    recorded_at: datetime


@dataclass(frozen=True)
class Conversion:
    amount: Decimal
    rate: Decimal  # montant converti pour une unité de la devise d'origine
    rate_date: date  # date du taux le plus ancien employé

    def is_stale(self, as_of: date) -> bool:
        return (as_of - self.rate_date).days > FX_STALE_AFTER_DAYS


@dataclass(frozen=True)
class _Leg:
    multiply: bool
    value: Decimal
    rate_date: date

    def apply(self, amount: Decimal) -> Decimal:
        return amount * self.value if self.multiply else amount / self.value


class FxTable:
    def __init__(self, rows: Iterable[FxRateRow]) -> None:
        grouped: dict[tuple[str, str], list[FxRateRow]] = defaultdict(list)
        for row in rows:
            grouped[(row.base, row.quote)].append(row)
        self._rows: dict[tuple[str, str], list[FxRateRow]] = {}
        self._dates: dict[tuple[str, str], list[date]] = {}
        for pair, pair_rows in grouped.items():
            ordered = sorted(pair_rows, key=lambda r: (r.effective_from, r.recorded_at))
            kept: list[FxRateRow] = []
            for row in ordered:  # à clé égale, la première reçue l'emporte
                if not kept or (kept[-1].effective_from, kept[-1].recorded_at) != (
                    row.effective_from,
                    row.recorded_at,
                ):
                    kept.append(row)
            self._rows[pair] = kept
            self._dates[pair] = [row.effective_from for row in kept]

    def _latest(self, pair: tuple[str, str], as_of: date) -> FxRateRow | None:
        dates = self._dates.get(pair)
        if not dates:
            return None
        index = bisect_right(dates, as_of)
        return self._rows[pair][index - 1] if index else None

    def _leg(self, source: str, target: str, as_of: date) -> _Leg | None:
        direct = self._latest((source, target), as_of)
        if direct is not None:
            return _Leg(True, direct.value, direct.effective_from)
        inverse = self._latest((target, source), as_of)
        if inverse is not None:
            return _Leg(False, inverse.value, inverse.effective_from)
        return None

    def convert(self, amount: Decimal, source: str, target: str, as_of: date) -> Conversion | None:
        """`amount` en `source` converti en `target` ; `None` si un taux manque."""
        if source == target:
            return Conversion(amount, Decimal(1), as_of)
        legs: list[_Leg] = []
        direct = self._leg(source, target, as_of)
        if direct is not None:
            legs = [direct]
        elif PIVOT not in (source, target):
            first, second = self._leg(source, PIVOT, as_of), self._leg(PIVOT, target, as_of)
            if first is None or second is None:
                return None
            legs = [first, second]
        else:
            return None
        with localcontext() as context:
            context.prec = PRECISION
            converted, rate = amount, Decimal(1)
            for leg in legs:
                converted, rate = leg.apply(converted), leg.apply(rate)
            converted = converted.quantize(_SCALE, rounding=ROUND_HALF_UP)
        return Conversion(converted, rate, min(leg.rate_date for leg in legs))
