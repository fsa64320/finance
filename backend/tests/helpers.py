"""Constructeurs de lignes valides pour les tests de schéma."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import (
    AccountType,
    InstrumentKind,
    PriceKind,
    PriceMode,
    PriceSource,
    RateKind,
    RateSource,
    TransactionType,
)

NOW = datetime(2026, 1, 6, 12, 0, tzinfo=UTC)


def make_account(session: Session, name: str | None = None, **overrides: object) -> models.Account:
    values: dict[str, object] = {
        "type": AccountType.PEA,
        "name": name or f"Compte {uuid4().hex[:8]}",
        "institution": "Courtier A",
        "currency": "EUR",
        "opened_on": date(2026, 1, 2),
        "settings": {"deposit_cap": "150000"},
    }
    values.update(overrides)
    account = models.Account(**values)
    session.add(account)
    session.flush()
    return account


def make_instrument(
    session: Session, name: str | None = None, **overrides: object
) -> models.Instrument:
    values: dict[str, object] = {
        "kind": InstrumentKind.ETF,
        "name": name or f"Actif {uuid4().hex[:8]}",
        "isin": None,
        "currency": "EUR",
        "price_mode": PriceMode.AUTO,
    }
    values.update(overrides)
    instrument = models.Instrument(**values)
    session.add(instrument)
    session.flush()
    return instrument


def make_transaction(session: Session, account: models.Account) -> models.Transaction:
    transaction = models.Transaction(account_id=account.id)
    session.add(transaction)
    session.flush()
    return transaction


def make_version(
    session: Session,
    transaction: models.Transaction,
    version: int = 1,
    **overrides: object,
) -> models.TransactionVersion:
    values: dict[str, object] = {
        "transaction_id": transaction.id,
        "version": version,
        "voided": False,
        "type": TransactionType.DEPOSIT,
        "trade_date": date(2026, 1, 5),
        "fees": Decimal(0),
        "cash_amount": Decimal("1000"),
        "currency": "EUR",
    }
    values.update(overrides)
    row = models.TransactionVersion(**values)
    session.add(row)
    session.flush()
    return row


def make_transfer_group(session: Session) -> models.TransferGroup:
    group = models.TransferGroup()
    session.add(group)
    session.flush()
    return group


def make_price(session: Session, instrument: models.Instrument) -> models.Price:
    price = models.Price(
        instrument_id=instrument.id,
        price_date=date(2026, 1, 6),
        kind=PriceKind.MARKET,
        value=Decimal("90.2"),
        currency="EUR",
        source=PriceSource.MANUAL,
    )
    session.add(price)
    session.flush()
    return price


def make_declared_balance(
    session: Session, account: models.Account, instrument: models.Instrument
) -> models.DeclaredBalance:
    balance = models.DeclaredBalance(
        account_id=account.id,
        instrument_id=instrument.id,
        balance_date=date(2026, 1, 1),
        amount=Decimal("5000"),
        currency="EUR",
    )
    session.add(balance)
    session.flush()
    return balance


def make_rate(session: Session) -> models.Rate:
    rate = models.Rate(
        kind=RateKind.LIVRET_A,
        effective_from=date(2026, 2, 1),
        value=Decimal("1.5"),
        source=RateSource.MANUAL,
    )
    session.add(rate)
    session.flush()
    return rate


def make_import_batch(session: Session, account: models.Account) -> models.ImportBatch:
    batch = models.ImportBatch(
        account_id=account.id,
        file_name="courtier_a.csv",
        file_hash="0" * 64,
        rows_added=50,
        rows_skipped=0,
        rows_rejected=0,
    )
    session.add(batch)
    session.flush()
    return batch
