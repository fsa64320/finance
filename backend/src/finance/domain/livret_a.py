"""Intérêts estimés du Livret A (FR-009, research.md §8).

Règle : l'intérêt d'une quinzaine (du 1er au 15, du 16 à la fin du mois) vaut le solde minimum de la
quinzaine x taux annuel / 24. Un dépôt ne compte qu'à partir de la quinzaine qui suit, un retrait
dès la quinzaine en cours : le solde minimum est le plus bas des soldes de fin de journée, de la
veille du premier jour au dernier jour de la quinzaine.

Les intérêts de l'année s'additionnent sans arrondi (une seule division par 2400 en fin de somme)
puis sont arrondis au centime, demi supérieur, au crédit du 31 décembre ; le crédit entre dans le
solde des quinzaines suivantes. L'intérêt couru de l'année en cours n'est pas arrondi (10
décimales). Le taux retenu est celui en vigueur au premier jour de la quinzaine.

Deux écarts avec la pratique des banques, à valider contre de vrais relevés avant de s'y fier : le
solde n'est pas tronqué à l'euro, et l'arrondi se fait une fois par an plutôt que par quinzaine.

Un intérêt réel saisi (type INTEREST) dans une année remplace l'estimation de cette année, à
partir de sa date. Il doit donc être daté dans l'année qu'il rémunère (en général le 31 décembre).
"""

import calendar
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext

from finance.domain.entries import Entry
from finance.domain.enums import TransactionType

PERIODS_PER_YEAR = 24
PRECISION = 50
_DENOMINATOR = Decimal(100 * PERIODS_PER_YEAR)  # pourcentage et quinzaines
_CENT = Decimal("0.01")
_SCALE = Decimal("1e-10")


@dataclass(frozen=True)
class RateRow:
    effective_from: date
    value: Decimal  # taux annuel en pourcentage
    recorded_at: datetime


@dataclass(frozen=True)
class Flow:
    on: date
    amount: Decimal  # signé : dépôt positif, retrait négatif
    real_interest: bool = False


@dataclass(frozen=True)
class InterestEstimate:
    credited: Decimal  # intérêts des années closes, déjà crédités
    accrued: Decimal  # intérêts courus de l'année en cours (quinzaines terminées)
    missing_rate_from: date | None  # première quinzaine à solde positif sans taux connu

    @property
    def total(self) -> Decimal:
        return self.credited + self.accrued


@dataclass(frozen=True)
class _Quinzaine:
    start: date
    end: date
    weighted: Decimal | None  # solde minimum x taux ; None si le taux manque


def _bounds(on: date) -> tuple[date, date]:
    if on.day <= 15:
        return date(on.year, on.month, 1), date(on.year, on.month, 15)
    return date(on.year, on.month, 16), date(
        on.year, on.month, calendar.monthrange(on.year, on.month)[1]
    )


def _rate_at(ordered: Sequence[RateRow], dates: Sequence[date], on: date) -> Decimal | None:
    index = bisect_right(dates, on)
    return ordered[index - 1].value if index else None


class LivretASchedule:
    """Intérêts estimés, calculés une fois puis lus à toute date jusqu'à `until`."""

    def __init__(
        self,
        quinzaines: list[_Quinzaine],
        credits: dict[int, Decimal],
        first_real: dict[int, date],
        until: date,
    ) -> None:
        self._quinzaines = quinzaines
        self._credits = credits  # année -> intérêts crédités le 31 décembre
        self._first_real = first_real
        self._until = until

    @classmethod
    def from_entries(
        cls, entries: Iterable[Entry], account_id: str, rates: Sequence[RateRow], *, until: date
    ) -> "LivretASchedule":
        flows = [
            Flow(e.trade_date, e.cash_amount, e.type is TransactionType.INTEREST)
            for e in entries
            if e.account_id == account_id and not e.voided
        ]
        return cls.build(flows, rates, until=until)

    @classmethod
    def build(
        cls, flows: Iterable[Flow], rates: Sequence[RateRow], *, until: date
    ) -> "LivretASchedule":
        ordered = sorted((f for f in flows if f.on <= until), key=lambda f: f.on)
        first_real: dict[int, date] = {}
        for flow in ordered:
            if flow.real_interest:
                first_real.setdefault(flow.on.year, flow.on)
        quinzaines: list[_Quinzaine] = []
        credits: dict[int, Decimal] = {}
        if not ordered:
            return cls(quinzaines, credits, first_real, until)

        ordered_rates = sorted(rates, key=lambda r: (r.effective_from, r.recorded_at))
        rate_dates = [r.effective_from for r in ordered_rates]
        balance = Decimal(0)
        cursor = 0
        year_weighted = Decimal(0)
        start, end = _bounds(ordered[0].on)
        while end <= until:
            minimum = balance
            while cursor < len(ordered) and ordered[cursor].on <= end:
                balance += ordered[cursor].amount
                minimum = min(minimum, balance)
                cursor += 1
            minimum = max(minimum, Decimal(0))
            rate = _rate_at(ordered_rates, rate_dates, start)
            weighted = None if rate is None else minimum * rate
            if rate is None and minimum == 0:
                weighted = Decimal(0)  # rien à rémunérer : le taux manquant est sans effet
            quinzaines.append(_Quinzaine(start, end, weighted))
            year_weighted += weighted or Decimal(0)
            if end.month == 12 and end.day == 31:
                if end.year not in first_real:
                    with localcontext() as context:
                        context.prec = PRECISION
                        credit = (year_weighted / _DENOMINATOR).quantize(
                            _CENT, rounding=ROUND_HALF_UP
                        )
                    credits[end.year] = credit
                    balance += credit
                year_weighted = Decimal(0)
            start = end + timedelta(days=1)
            end = _bounds(start)[1]
        return cls(quinzaines, credits, first_real, until)

    def estimate_at(self, as_of: date) -> InterestEstimate:
        if as_of > self._until:
            raise ValueError("La date dépasse celle jusqu'à laquelle l'estimation a été préparée.")
        credited = sum(
            (amount for year, amount in self._credits.items() if date(year, 12, 31) <= as_of),
            Decimal(0),
        )
        weighted = Decimal(0)
        missing: date | None = None
        for item in self._quinzaines:
            if item.end > as_of:
                break
            if item.weighted is None and missing is None:
                missing = item.start
            year = item.end.year
            real = self._first_real.get(year)
            if (
                item.weighted is not None
                and date(year, 12, 31) > as_of
                and (real is None or real > as_of)
            ):
                weighted += item.weighted
        with localcontext() as context:
            context.prec = PRECISION
            accrued = (weighted / _DENOMINATOR).quantize(_SCALE, rounding=ROUND_HALF_UP)
        return InterestEstimate(credited=credited, accrued=accrued, missing_rate_from=missing)
