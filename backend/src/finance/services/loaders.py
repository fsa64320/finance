"""Lecture du journal et des données de valorisation, convertis en objets du domaine."""

from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.entries import Entry
from finance.domain.valuation import DeclaredBalanceRow, InstrumentInfo, PricePoint


def entry_from_row(version: models.TransactionVersion) -> Entry:
    return Entry(
        transaction_id=version.transaction_id,
        version=version.version,
        account_id=version.transaction.account_id,
        type=version.type,
        trade_date=version.trade_date,
        cash_amount=version.cash_amount,
        currency=version.currency,
        created_at=version.transaction.created_at,
        voided=version.voided,
        instrument_id=version.instrument_id,
        quantity=version.quantity,
        unit_price=version.unit_price,
        fees=version.fees,
        unlock_date=version.unlock_date,
        transfer_group_id=version.transfer_group_id,
        label=version.label,
    )


def latest_versions_statement() -> sa.Select[Any]:
    """Dernière version de chaque opération."""
    newest = (
        sa.select(
            models.TransactionVersion.transaction_id.label("transaction_id"),
            sa.func.max(models.TransactionVersion.version).label("version"),
        )
        .group_by(models.TransactionVersion.transaction_id)
        .subquery()
    )
    return sa.select(models.TransactionVersion).join(
        newest,
        sa.and_(
            models.TransactionVersion.transaction_id == newest.c.transaction_id,
            models.TransactionVersion.version == newest.c.version,
        ),
    )


def load_entries(
    session: Session, *, account_ids: Iterable[str] | None = None, include_voided: bool = False
) -> list[Entry]:
    """Opérations en vigueur (dernière version) des comptes demandés, tous comptes par défaut."""
    statement = latest_versions_statement().join(
        models.Transaction, models.Transaction.id == models.TransactionVersion.transaction_id
    )
    if account_ids is not None:
        statement = statement.where(models.Transaction.account_id.in_(list(account_ids)))
    if not include_voided:
        statement = statement.where(models.TransactionVersion.voided.is_(False))
    return [entry_from_row(row) for row in session.scalars(statement).unique()]


def load_instrument_infos(session: Session) -> dict[str, InstrumentInfo]:
    return {
        row.id: InstrumentInfo(id=row.id, kind=row.kind, currency=row.currency)
        for row in session.scalars(sa.select(models.Instrument))
    }


def load_prices(session: Session) -> list[PricePoint]:
    return [
        PricePoint(
            instrument_id=row.instrument_id,
            price_date=row.price_date,
            kind=row.kind,
            value=row.value,
            currency=row.currency,
            recorded_at=row.recorded_at,
        )
        for row in session.scalars(sa.select(models.Price))
    ]


def load_declared_balances(session: Session) -> list[DeclaredBalanceRow]:
    return [
        DeclaredBalanceRow(
            account_id=row.account_id,
            instrument_id=row.instrument_id,
            balance_date=row.balance_date,
            amount=row.amount,
            currency=row.currency,
            recorded_at=row.recorded_at,
        )
        for row in session.scalars(sa.select(models.DeclaredBalance))
    ]
