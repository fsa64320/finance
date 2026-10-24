"""Fabriques d'opérations pour les tests du domaine. Les montants sont calculés ici à la main,
indépendamment du code testé."""

import itertools
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from finance.domain.entries import Entry

from finance.domain.enums import TransactionType

_ids = itertools.count(1)
_BASE = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def d(value: str) -> Decimal:
    return Decimal(value)


def day(text: str) -> date:
    return date.fromisoformat(text)


def make(
    kind: TransactionType,
    on: str,
    *,
    cash: str,
    account: str = "a1",
    instrument: str | None = None,
    quantity: str | None = None,
    unit_price: str | None = None,
    fees: str = "0",
    version: int = 1,
    voided: bool = False,
    transaction_id: str | None = None,
    currency: str = "EUR",
    unlock: str | None = None,
    group: str | None = None,
) -> Entry:
    number = next(_ids)
    return Entry(
        transaction_id=transaction_id or f"t{number}",
        version=version,
        account_id=account,
        type=kind,
        trade_date=day(on),
        cash_amount=d(cash),
        currency=currency,
        created_at=_BASE + timedelta(seconds=number),
        voided=voided,
        instrument_id=instrument,
        quantity=None if quantity is None else d(quantity),
        unit_price=None if unit_price is None else d(unit_price),
        fees=d(fees),
        unlock_date=None if unlock is None else day(unlock),
        transfer_group_id=group,
    )


def deposit(amount: str, on: str, **kw: object) -> Entry:
    return make(TransactionType.DEPOSIT, on, cash=amount, **kw)  # type: ignore[arg-type]


def withdrawal(amount: str, on: str, **kw: object) -> Entry:
    return make(TransactionType.WITHDRAWAL, on, cash=f"-{amount}", **kw)  # type: ignore[arg-type]


def buy(
    quantity: str, price: str, on: str, fees: str = "0", instrument: str = "etf", **kw: object
) -> Entry:
    spent = d(quantity) * d(price) + d(fees)
    return make(
        TransactionType.BUY,
        on,
        cash=f"-{spent}",
        instrument=instrument,
        quantity=quantity,
        unit_price=price,
        fees=fees,
        **kw,  # type: ignore[arg-type]
    )


def sell(
    quantity: str, price: str, on: str, fees: str = "0", instrument: str = "etf", **kw: object
) -> Entry:
    received = d(quantity) * d(price) - d(fees)
    return make(
        TransactionType.SELL,
        on,
        cash=str(received),
        instrument=instrument,
        quantity=quantity,
        unit_price=price,
        fees=fees,
        **kw,  # type: ignore[arg-type]
    )


# ------------------------------------------------------------------ valorisation
from finance.domain.valuation import DeclaredBalanceRow, InstrumentInfo, PricePoint  # noqa: E402

from finance.domain.enums import InstrumentKind, PriceKind  # noqa: E402


def instrument(identifier: str, kind: InstrumentKind, currency: str = "EUR") -> InstrumentInfo:
    return InstrumentInfo(id=identifier, kind=kind, currency=currency)


def price(
    instrument_id: str,
    on: str,
    value: str,
    kind: PriceKind = PriceKind.MARKET,
    recorded: int = 0,
    currency: str = "EUR",
) -> PricePoint:
    return PricePoint(
        instrument_id=instrument_id,
        price_date=day(on),
        kind=kind,
        value=d(value),
        currency=currency,
        recorded_at=_BASE + timedelta(minutes=recorded),
    )


def declared(
    instrument_id: str,
    on: str,
    amount: str,
    recorded: int = 0,
    account: str = "a1",
    currency: str = "EUR",
) -> DeclaredBalanceRow:
    return DeclaredBalanceRow(
        account_id=account,
        instrument_id=instrument_id,
        balance_date=day(on),
        amount=d(amount),
        currency=currency,
        recorded_at=_BASE + timedelta(minutes=recorded),
    )
