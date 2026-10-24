"""Tableau de bord : patrimoine net, évolution et répartition (FR-021 à FR-025).

Tout est recalculé depuis le journal, les prix et les soldes déclarés. Un cache mémoire évite de
refaire le calcul entre deux écritures ; il est vidé à chaque validation d'une écriture et peut
toujours être reconstruit à l'identique (principe II : aucune valeur dérivée n'est stockée).
"""

import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.allocation import Slice, compute_allocation
from finance.domain.networth import AccountRef, NetWorth, compute_net_worth
from finance.domain.series import SeriesPoint, net_worth_series, period_start, sample_dates
from finance.services import loaders
from finance.services.accounts import REFERENCE_CURRENCY
from finance.services.errors import ValidationFailed

PERIODS = ("1m", "3m", "1y", "5y", "all")

_NOTICE_KINDS = {
    "price_missing": "stale_price",
    "declared_balance_missing": "missing_balance",
    "non_convertible": "missing_fx",
    "negative_position": "negative_position",
}


@dataclass(frozen=True)
class Notice:
    kind: str
    message: str
    instrument_id: str | None
    account_id: str | None


@dataclass(frozen=True)
class Summary:
    currency: str
    net_worth: Decimal
    estimated: bool
    as_of: date
    notices: tuple[Notice, ...]
    excludes_debts: bool = True


@dataclass(frozen=True)
class SeriesResult:
    currency: str
    points: list[SeriesPoint]


@dataclass(frozen=True)
class AllocationResult:
    currency: str
    slices: list[Slice]


# ------------------------------------------------------------------------ cache


@dataclass
class _EngineCache:
    version: int = 0
    store: dict[tuple[Any, ...], tuple[int, Any]] = field(default_factory=dict)


_caches: "weakref.WeakKeyDictionary[Any, _EngineCache]" = weakref.WeakKeyDictionary()
_WRITTEN = "dashboard_written"


def _cache_for(session: Session) -> _EngineCache:
    bind = session.get_bind()
    cache = _caches.get(bind)
    if cache is None:
        cache = _EngineCache()
        _caches[bind] = cache
    return cache


def clear_cache() -> None:
    _caches.clear()


@event.listens_for(Session, "after_flush")
def _mark_written(session: Session, _: object) -> None:
    session.info[_WRITTEN] = True


@event.listens_for(Session, "after_commit")
def _invalidate_on_commit(session: Session) -> None:
    if session.info.pop(_WRITTEN, False):
        cache = _cache_for(session)
        cache.version += 1
        cache.store.clear()


@event.listens_for(Session, "after_rollback")
def _forget_rolled_back_writes(session: Session) -> None:
    session.info.pop(_WRITTEN, None)


def _cached(session: Session, key: tuple[Any, ...], compute: Callable[[], Any]) -> Any:
    if session.info.get(_WRITTEN):
        return compute()  # écritures non validées dans cette session : ne pas figer le résultat
    cache = _cache_for(session)
    hit = cache.store.get(key)
    if hit is not None and hit[0] == cache.version:
        return hit[1]
    value = compute()
    cache.store[key] = (cache.version, value)
    return value


# ---------------------------------------------------------------------- données


@dataclass
class _Inputs:
    refs: list[AccountRef]
    entries: list[Any]
    instruments: dict[str, Any]
    prices: list[Any]
    balances: list[Any]


def _load(session: Session) -> _Inputs:
    rows = session.scalars(sa.select(models.Account).order_by(models.Account.opened_on)).all()
    return _Inputs(
        refs=[AccountRef(r.id, r.opened_on, r.closed_on, r.currency) for r in rows],
        entries=loaders.load_entries(session),
        instruments=loaders.load_instrument_infos(session),
        prices=loaders.load_prices(session),
        balances=loaders.load_declared_balances(session),
    )


def _net_worth(inputs: _Inputs, as_of: date) -> NetWorth:
    return compute_net_worth(
        refs=inputs.refs,
        entries=inputs.entries,
        instruments=inputs.instruments,
        prices=inputs.prices,
        balances=inputs.balances,
        as_of=as_of,
        currency=REFERENCE_CURRENCY,
    )


# --------------------------------------------------------------------- services


def summary(session: Session, as_of: date) -> Summary:
    def compute() -> Summary:
        worth = _net_worth(_load(session), as_of)
        notices = tuple(
            Notice(
                kind=_NOTICE_KINDS.get(w.code, w.code),
                message=w.message,
                instrument_id=w.instrument_id,
                account_id=w.account_id,
            )
            for w in worth.warnings
        )
        return Summary(
            currency=worth.currency,
            net_worth=worth.total,
            estimated=worth.estimated,
            as_of=as_of,
            notices=notices,
        )

    result: Summary = _cached(session, ("summary", as_of), compute)
    return result


def allocation(session: Session, as_of: date) -> AllocationResult:
    def compute() -> AllocationResult:
        worth = _net_worth(_load(session), as_of)
        return AllocationResult(
            currency=worth.currency, slices=compute_allocation(worth.account_values)
        )

    result: AllocationResult = _cached(session, ("allocation", as_of), compute)
    return result


def series(session: Session, period: str, today: date) -> SeriesResult:
    if period not in PERIODS:
        raise ValidationFailed.single("period", "La période doit être 1m, 3m, 1y, 5y ou all.")

    def compute() -> SeriesResult:
        inputs = _load(session)
        if not inputs.refs:
            return SeriesResult(currency=REFERENCE_CURRENCY, points=[])
        earliest = min(
            [r.opened_on for r in inputs.refs]
            + [e.trade_date for e in inputs.entries]
            + [b.balance_date for b in inputs.balances]
        )
        start = period_start(period, today, earliest=earliest)
        points = net_worth_series(
            refs=inputs.refs,
            entries=inputs.entries,
            instruments=inputs.instruments,
            prices=inputs.prices,
            balances=inputs.balances,
            dates=sample_dates(start, today),
            currency=REFERENCE_CURRENCY,
        )
        return SeriesResult(currency=REFERENCE_CURRENCY, points=points)

    result: SeriesResult = _cached(session, ("series", period, today), compute)
    return result
