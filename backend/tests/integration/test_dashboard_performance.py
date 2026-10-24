"""SC-004 : 10 ans d'historique et 5 000 opérations, série calculée en moins de 3 secondes."""

import random
import time
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import (
    AccountType,
    InstrumentKind,
    PriceKind,
    PriceSource,
    TransactionType,
)
from finance.services import dashboard

TODAY = date(2026, 10, 24)
START = date(2016, 10, 24)


def fill(session: Session) -> int:
    """Insère directement 5 000 opérations réparties sur 3 comptes et 10 actifs."""
    rng = random.Random(7)  # noqa: S311 - données de test reproductibles
    accounts = [
        models.Account(
            type=AccountType.CTO, name=f"Compte {n}", currency="EUR", opened_on=START, settings={}
        )
        for n in range(3)
    ]
    assets = [
        models.Instrument(kind=InstrumentKind.ETF, name=f"ETF {n}", currency="EUR")
        for n in range(10)
    ]
    session.add_all([*accounts, *assets])
    session.flush()

    rows: list[object] = []

    def operation(account: models.Account, **fields: object) -> None:
        identifier = str(uuid4())
        rows.append(models.Transaction(id=identifier, account_id=account.id))
        rows.append(
            models.TransactionVersion(
                transaction_id=identifier,
                version=1,
                currency="EUR",
                **fields,  # type: ignore[arg-type]
            )
        )

    for account in accounts:
        operation(
            account, type=TransactionType.DEPOSIT, trade_date=START, cash_amount=Decimal("200000")
        )
    days = (TODAY - START).days
    for _ in range(4997):
        asset = rng.choice(assets)
        quantity = Decimal(rng.randint(1, 20))
        unit = Decimal(rng.randint(20, 400))
        buying = rng.random() < 0.65
        operation(
            rng.choice(accounts),
            type=TransactionType.BUY if buying else TransactionType.SELL,
            trade_date=START + timedelta(days=rng.randint(1, days)),
            instrument_id=asset.id,
            quantity=quantity,
            unit_price=unit,
            fees=Decimal(1),
            cash_amount=-(quantity * unit + 1) if buying else quantity * unit - 1,
        )
    session.add_all(rows)
    for asset in assets:
        for offset in range(0, days, 7):
            session.add(
                models.Price(
                    instrument_id=asset.id,
                    price_date=START + timedelta(days=offset),
                    kind=PriceKind.MARKET,
                    value=Decimal(rng.randint(20, 400)),
                    currency="EUR",
                    source=PriceSource.MANUAL,
                )
            )
    session.commit()
    return len(rows) // 2


def test_ten_years_and_five_thousand_operations_stay_under_three_seconds(session: Session) -> None:
    total = fill(session)
    assert total == 5000

    started = time.perf_counter()
    result = dashboard.series(session, "all", TODAY)
    elapsed = time.perf_counter() - started

    assert len(result.points) >= 520
    assert result.points[-1].date == TODAY
    assert elapsed < 3.0, f"série en {elapsed:.2f} s"


def test_summary_and_allocation_are_fast_too(session: Session) -> None:
    fill(session)
    started = time.perf_counter()
    dashboard.summary(session, TODAY)
    dashboard.allocation(session, TODAY)
    assert time.perf_counter() - started < 3.0
