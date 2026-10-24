"""Principe II : le journal ne reçoit ni UPDATE ni DELETE, ni par l'ORM, ni en SQL brut."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from finance.db import models
from finance.db.append_only import PROTECTED_TABLES, AppendOnlyError
from tests import helpers

Factory = Callable[[Session], object]


def build_transaction(session: Session) -> models.Transaction:
    return helpers.make_transaction(session, helpers.make_account(session))


def build_version(session: Session) -> models.TransactionVersion:
    return helpers.make_version(session, build_transaction(session))


def build_price(session: Session) -> models.Price:
    return helpers.make_price(session, helpers.make_instrument(session))


def build_balance(session: Session) -> models.DeclaredBalance:
    account = helpers.make_account(session)
    instrument = helpers.make_instrument(
        session, kind="EURO_FUND", isin=None, name="Fonds en euros"
    )
    return helpers.make_declared_balance(session, account, instrument)


def build_batch(session: Session) -> models.ImportBatch:
    return helpers.make_import_batch(session, helpers.make_account(session))


# (table, modèle, fabrique, colonne à modifier, valeur de remplacement)
CASES: list[tuple[str, type, Factory, str, object]] = [
    ("transaction", models.Transaction, build_transaction, "account_id", "autre"),
    ("transaction_version", models.TransactionVersion, build_version, "label", "modifié"),
    ("transfer_group", models.TransferGroup, helpers.make_transfer_group, "id", "autre"),
    ("price", models.Price, build_price, "value", Decimal("1")),
    ("declared_balance", models.DeclaredBalance, build_balance, "amount", Decimal("1")),
    ("rate", models.Rate, helpers.make_rate, "value", Decimal("2")),
    ("import_batch", models.ImportBatch, build_batch, "rows_added", 0),
]
IDS = [case[0] for case in CASES]


def test_protected_tables_are_exactly_the_journal_tables() -> None:
    assert {case[0] for case in CASES} == set(PROTECTED_TABLES)
    assert {
        "transaction_version",
        "price",
        "declared_balance",
        "rate",
        "import_batch",
    } <= set(PROTECTED_TABLES)


@pytest.mark.parametrize(("table", "model", "factory", "column", "value"), CASES, ids=IDS)
def test_orm_update_is_refused(
    session: Session, table: str, model: type, factory: Factory, column: str, value: object
) -> None:
    row = factory(session)
    session.commit()
    setattr(row, column, value)
    with pytest.raises(AppendOnlyError, match=table):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(("table", "model", "factory", "column", "value"), CASES, ids=IDS)
def test_orm_delete_is_refused(
    session: Session, table: str, model: type, factory: Factory, column: str, value: object
) -> None:
    row = factory(session)
    session.commit()
    session.delete(row)
    with pytest.raises(AppendOnlyError, match=table):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(("table", "model", "factory", "column", "value"), CASES, ids=IDS)
def test_bulk_orm_statements_are_refused(
    session: Session, table: str, model: type, factory: Factory, column: str, value: object
) -> None:
    factory(session)
    session.commit()
    with pytest.raises(AppendOnlyError, match=table):
        session.execute(sa.update(model).values({column: value}))
    with pytest.raises(AppendOnlyError, match=table):
        session.execute(sa.delete(model))
    session.rollback()


@pytest.mark.parametrize(("table", "model", "factory", "column", "value"), CASES, ids=IDS)
def test_raw_sql_is_refused_by_the_database(
    session: Session, table: str, model: type, factory: Factory, column: str, value: object
) -> None:
    factory(session)
    session.commit()
    connection = session.get_bind().connect()
    try:
        with pytest.raises(DatabaseError, match="append-only"):
            connection.execute(sa.text(f'UPDATE "{table}" SET {column} = {column}'))  # noqa: S608 - table fixe
        connection.rollback()
        with pytest.raises(DatabaseError, match="append-only"):
            connection.execute(sa.text(f'DELETE FROM "{table}"'))  # noqa: S608 - table fixe
        connection.rollback()
    finally:
        connection.close()


@pytest.mark.parametrize(("table", "model", "factory", "column", "value"), CASES, ids=IDS)
def test_inserting_is_allowed_and_rows_are_kept(
    session: Session, table: str, model: type, factory: Factory, column: str, value: object
) -> None:
    before = session.scalar(sa.select(sa.func.count()).select_from(model))  # taux livrés compris
    factory(session)
    factory(session)
    session.commit()
    assert session.scalar(sa.select(sa.func.count()).select_from(model)) == (before or 0) + 2


def test_account_table_stays_editable(session: Session) -> None:
    account = helpers.make_account(session)
    session.commit()
    account.closed_on = date(2026, 6, 30)
    session.commit()
    assert session.get(models.Account, account.id).closed_on == date(2026, 6, 30)  # type: ignore[union-attr]
