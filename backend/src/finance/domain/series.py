"""Évolution du patrimoine dans le temps (FR-022).

La série se calcule par un balayage unique : les opérations, les prix et les soldes déclarés sont
triés une fois, puis consommés au fil des dates. Le résultat est identique, date par date, à un
recalcul complet par `compute_net_worth` (vérifié par un test de propriété).
"""

import calendar
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

from finance.domain.cost_basis import apply_trade
from finance.domain.entries import Entry
from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind
from finance.domain.enums import TransactionType as T
from finance.domain.fx import FxTable
from finance.domain.livret_a import Flow, LivretASchedule, RateRow
from finance.domain.networth import AccountRef, is_open_on
from finance.domain.valuation import (
    PRICE_KIND_BY_INSTRUMENT,
    DeclaredBalanceRow,
    InstrumentInfo,
    PricePoint,
    convert_amount,
    value_priced,
)

DAILY_LIMIT_DAYS = 366  # jusqu'à un an (année bissextile comprise) : un point par jour
WEEK = timedelta(days=7)
_MONTHS = {"1m": 1, "3m": 3, "1y": 12, "5y": 60}


@dataclass(frozen=True)
class SeriesPoint:
    date: date
    value: Decimal
    estimated: bool


def _months_back(on: date, months: int) -> date:
    index = on.year * 12 + (on.month - 1) - months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(on.day, calendar.monthrange(year, month)[1]))


def period_start(period: str, end: date, *, earliest: date | None) -> date:
    """Première date de la période demandée ("all" remonte à la première activité)."""
    if period == "all":
        return earliest if earliest is not None and earliest <= end else end
    if period not in _MONTHS:
        raise ValueError("La période doit être 1m, 3m, 1y, 5y ou all.")
    return _months_back(end, _MONTHS[period])


def sample_dates(start: date, end: date) -> list[date]:
    """Un point par jour jusqu'à un an, un par semaine au-delà ; toujours terminé par `end`."""
    if start > end:
        raise ValueError("La date de début suit la date de fin.")
    if (end - start).days <= DAILY_LIMIT_DAYS:
        return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    dates: list[date] = []
    current = start
    while current < end:
        dates.append(current)
        current += WEEK
    dates.append(end)
    return dates


@dataclass
class _AccountState:
    entries: list[Entry]
    cursor: int = 0
    cash: Decimal = Decimal(0)
    holdings: dict[str, tuple[Decimal, Decimal]] = field(default_factory=dict)
    traded: set[str] = field(default_factory=set)
    declared_ids: set[str] = field(default_factory=set)


@dataclass
class _Pointer:
    """Curseur sur une liste triée : `latest` est le dernier élément de date <= date courante."""

    rows: list[object]
    keys: list[date]
    index: int = 0

    def advance(self, until: date) -> object | None:
        while self.index < len(self.rows) and self.keys[self.index] <= until:
            self.index += 1
        return self.rows[self.index - 1] if self.index else None


def _first_of_each[Row](rows: Sequence[Row], key: Callable[[Row], object]) -> list[Row]:
    """Retire les lignes dont la clé répète celle de la précédente (liste déjà triée)."""
    kept: list[Row] = []
    for row in rows:
        if not kept or key(kept[-1]) != key(row):
            kept.append(row)
    return kept


def _flow(entry: Entry) -> Decimal:
    amount = (entry.quantity or Decimal(0)) * (entry.unit_price or Decimal(0))
    return amount if entry.type is T.BUY else -amount


def net_worth_series(
    *,
    refs: Sequence[AccountRef],
    entries: Sequence[Entry],
    instruments: Mapping[str, InstrumentInfo],
    prices: Sequence[PricePoint],
    balances: Sequence[DeclaredBalanceRow],
    dates: Sequence[date],
    currency: str,
    fx: FxTable | None = None,
    livret_rates: Sequence[RateRow] = (),
) -> list[SeriesPoint]:
    """Valeur du patrimoine à chacune des `dates` (strictement croissantes)."""
    if any(later <= earlier for earlier, later in pairwise(dates)):
        raise ValueError("Les dates doivent être en ordre croissant.")
    if not refs:
        return []

    states: dict[str, _AccountState] = {}
    for ref in refs:
        mine = [e for e in entries if e.account_id == ref.id and not e.voided]
        mine.sort(key=lambda e: (e.trade_date, e.created_at, e.transaction_id))
        states[ref.id] = _AccountState(entries=mine)

    schedules = {
        ref.id: LivretASchedule.build(
            [
                Flow(e.trade_date, e.cash_amount, e.type is T.INTEREST)
                for e in states[ref.id].entries
            ],
            livret_rates,
            until=dates[-1],
        )
        for ref in refs
        if ref.is_livret_a
    }

    # Flux cumulés des fonds en euros, indexés par date pour retrouver les flux entre deux dates.
    flow_dates: dict[tuple[str, str], list[date]] = defaultdict(list)
    flow_totals: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for ref in refs:
        running: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for entry in states[ref.id].entries:
            if entry.type in {T.BUY, T.SELL} and entry.instrument_id is not None:
                running[entry.instrument_id] += _flow(entry)
                key = (ref.id, entry.instrument_id)
                flow_dates[key].append(entry.trade_date)
                flow_totals[key].append(running[entry.instrument_id])

    def cumulative(key: tuple[str, str], upto: date) -> Decimal:
        position = bisect_right(flow_dates.get(key, []), upto)
        return flow_totals[key][position - 1] if position else Decimal(0)

    balance_pointers: dict[tuple[str, str], _Pointer] = {}
    grouped_balances: dict[tuple[str, str], list[DeclaredBalanceRow]] = defaultdict(list)
    for balance in balances:
        grouped_balances[(balance.account_id, balance.instrument_id)].append(balance)
        if balance.account_id in states:
            states[balance.account_id].declared_ids.add(balance.instrument_id)
    for key, balance_rows in grouped_balances.items():
        # Tri stable ; à clé égale, la première ligne reçue l'emporte, comme dans `value_account`.
        ordered_balances = _first_of_each(
            sorted(balance_rows, key=lambda b: (b.balance_date, b.recorded_at)),
            lambda b: (b.balance_date, b.recorded_at),
        )
        balance_pointers[key] = _Pointer(
            list(ordered_balances), [b.balance_date for b in ordered_balances]
        )

    price_pointers: dict[tuple[str, PriceKind], _Pointer] = {}
    grouped_prices: dict[tuple[str, PriceKind], list[PricePoint]] = defaultdict(list)
    for point in prices:
        grouped_prices[(point.instrument_id, point.kind)].append(point)
    for key2, price_rows in grouped_prices.items():
        ordered_prices = _first_of_each(
            sorted(price_rows, key=lambda p: (p.price_date, p.recorded_at)),
            lambda p: (p.price_date, p.recorded_at),
        )
        price_pointers[key2] = _Pointer(
            list(ordered_prices), [p.price_date for p in ordered_prices]
        )

    points: list[SeriesPoint] = []
    for current in dates:
        total = Decimal(0)
        estimated = False
        for ref in refs:
            state = states[ref.id]
            while (
                state.cursor < len(state.entries)
                and state.entries[state.cursor].trade_date <= current
            ):
                entry = state.entries[state.cursor]
                state.cursor += 1
                state.cash += entry.cash_amount
                if entry.type in {T.BUY, T.SELL} and entry.instrument_id is not None:
                    quantity, cost = state.holdings.get(
                        entry.instrument_id, (Decimal(0), Decimal(0))
                    )
                    state.holdings[entry.instrument_id] = apply_trade(quantity, cost, entry)
                    state.traded.add(entry.instrument_id)
            if not is_open_on(ref, current):
                continue

            account_total = state.cash
            account_estimated = False
            schedule = schedules.get(ref.id)
            if schedule is not None:
                interest = schedule.estimate_at(current)
                account_total += interest.total
                account_estimated = interest.total != 0 or interest.missing_rate_from is not None
            for identifier in sorted(state.traded | state.declared_ids):
                if identifier not in instruments:
                    raise KeyError(f"actif inconnu : {identifier}")
                info = instruments[identifier]
                if info.kind is K.EURO_FUND:
                    pointer = balance_pointers.get((ref.id, identifier))
                    latest = pointer.advance(current) if pointer else None
                    if latest is None or not isinstance(latest, DeclaredBalanceRow):
                        account_estimated = True
                        continue
                    converted = convert_amount(
                        latest.amount, latest.currency, ref.currency, current, fx
                    )
                    if converted.value is None:
                        account_estimated = True
                        continue
                    account_estimated = account_estimated or converted.code == "rate_stale"
                    key = (ref.id, identifier)
                    account_total += converted.value + (
                        cumulative(key, current) - cumulative(key, latest.balance_date)
                    )
                elif info.kind is K.CASH:
                    continue
                else:
                    quantity, cost = state.holdings.get(identifier, (Decimal(0), Decimal(0)))
                    if quantity == 0:
                        continue
                    if quantity < 0:
                        account_estimated = True
                        continue
                    wanted = PRICE_KIND_BY_INSTRUMENT[info.kind]
                    price_pointer = price_pointers.get((identifier, wanted))
                    price = price_pointer.advance(current) if price_pointer else None
                    if price is not None and not isinstance(price, PricePoint):
                        raise TypeError("prix attendu")
                    priced = value_priced(
                        quantity=quantity,
                        total_cost=cost,
                        price=price,
                        currency=ref.currency,
                        as_of=current,
                        fx=fx,
                    )
                    account_estimated = account_estimated or priced.estimated
                    if priced.value is not None:
                        account_total += priced.value

            if ref.currency != currency:
                converted_total = convert_amount(account_total, ref.currency, currency, current, fx)
                if converted_total.value is None:
                    estimated = True
                    continue
                account_total = converted_total.value
                account_estimated = account_estimated or converted_total.code == "rate_stale"
            total += account_total
            estimated = estimated or account_estimated
        points.append(SeriesPoint(date=current, value=total, estimated=estimated))
    return points
