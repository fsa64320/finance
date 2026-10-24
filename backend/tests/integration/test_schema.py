"""data-model.md : contraintes du schéma, vérifiées sur la base chiffrée migrée."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import AccountType, TransactionType
from tests import helpers

EXPECTED_TABLES = {
    "account",
    "instrument",
    "transaction",
    "transaction_version",
    "transfer_group",
    "price",
    "declared_balance",
    "rate",
    "import_batch",
    "import_mapping",
    "setting",
}


def test_all_tables_exist(migrated_engine: sa.Engine) -> None:
    tables = set(sa.inspect(migrated_engine).get_table_names())
    assert EXPECTED_TABLES <= tables


def test_two_open_accounts_cannot_share_a_name(session: Session) -> None:
    helpers.make_account(session, "PEA Courtier A")
    session.commit()
    with pytest.raises(IntegrityError):
        helpers.make_account(session, "PEA Courtier A")
    session.rollback()


def test_a_closed_account_frees_its_name(session: Session) -> None:
    first = helpers.make_account(session, "PEA Courtier A")
    first.closed_on = date(2026, 6, 30)
    session.commit()
    helpers.make_account(session, "PEA Courtier A")
    session.commit()


def test_closing_before_opening_is_refused(session: Session) -> None:
    with pytest.raises(IntegrityError):
        helpers.make_account(session, closed_on=date(2025, 12, 31))
    session.rollback()


def test_account_settings_keep_their_json(session: Session) -> None:
    account = helpers.make_account(session, settings={"deposit_cap": "150000", "lock_years": 5})
    session.commit()
    session.expire_all()
    assert session.get(models.Account, account.id).settings == {  # type: ignore[union-attr]
        "deposit_cap": "150000",
        "lock_years": 5,
    }


def test_isin_is_unique_when_present(session: Session) -> None:
    helpers.make_instrument(session, isin="IE00B4L5Y983")
    session.commit()
    with pytest.raises(IntegrityError):
        helpers.make_instrument(session, isin="IE00B4L5Y983")
    session.rollback()


def test_several_instruments_may_have_no_isin(session: Session) -> None:
    helpers.make_instrument(session, isin=None)
    helpers.make_instrument(session, isin=None)
    session.commit()


def test_isin_must_have_twelve_characters(session: Session) -> None:
    with pytest.raises(IntegrityError):
        helpers.make_instrument(session, isin="IE00B4L5Y98")
    session.rollback()


def test_unknown_enum_values_are_refused_by_the_database(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.execute(
            sa.text(
                "INSERT INTO account (id, type, name, currency, opened_on, settings, created_at, updated_at) "
                "VALUES ('a1', 'LIVRET_B', 'x', 'EUR', '2026-01-02', '{}', '2026-01-02', '2026-01-02')"
            )
        )
    session.rollback()


def test_foreign_keys_are_enforced(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.add(models.Transaction(account_id="inconnu"))
        session.flush()
    session.rollback()


def test_transaction_version_numbering(session: Session) -> None:
    transaction = helpers.make_transaction(session, helpers.make_account(session))
    helpers.make_version(session, transaction, version=1)
    session.commit()
    with pytest.raises(IntegrityError):
        helpers.make_version(session, transaction, version=1)
    session.rollback()
    with pytest.raises(IntegrityError):
        helpers.make_version(session, transaction, version=0)
    session.rollback()


def test_transaction_version_keeps_exact_decimals(session: Session) -> None:
    account = helpers.make_account(session)
    instrument = helpers.make_instrument(session)
    transaction = helpers.make_transaction(session, account)
    helpers.make_version(
        session,
        transaction,
        type=TransactionType.BUY,
        instrument_id=instrument.id,
        quantity=Decimal("10"),
        unit_price=Decimal("90"),
        fees=Decimal("1.99"),
        cash_amount=Decimal("-901.99"),
    )
    session.commit()
    session.expire_all()
    row = session.get(models.TransactionVersion, (transaction.id, 1))
    assert row is not None
    assert (row.quantity, row.unit_price, row.fees, row.cash_amount) == (
        Decimal("10"),
        Decimal("90"),
        Decimal("1.99"),
        Decimal("-901.99"),
    )
    assert isinstance(row.cash_amount, Decimal)


def test_timestamps_are_stored_in_utc_and_come_back_aware(session: Session) -> None:
    account = helpers.make_account(session)
    session.commit()
    session.expire_all()
    created = session.get(models.Account, account.id).created_at  # type: ignore[union-attr]
    assert created.tzinfo is not None
    assert created.utcoffset() == datetime.now(UTC).utcoffset()


def test_naive_timestamps_are_refused(session: Session) -> None:
    transaction = helpers.make_transaction(session, helpers.make_account(session))
    session.commit()
    with pytest.raises((ValueError, StatementError)):
        helpers.make_version(session, transaction, created_at=datetime(2026, 1, 6, 12, 0))
    session.rollback()


def test_import_mapping_names_are_unique(session: Session) -> None:
    for _ in range(2):
        session.add(
            models.ImportMapping(
                name="Courtier A",
                delimiter=";",
                encoding="windows-1252",
                date_format="%d/%m/%Y",
                decimal_separator=",",
                columns={"date": "Date opération"},
            )
        )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_settings_store_key_values(session: Session) -> None:
    session.add(models.Setting(key="auto_fetch_prices", value="false"))
    session.commit()
    assert session.get(models.Setting, "auto_fetch_prices").value == "false"  # type: ignore[union-attr]


def test_account_type_round_trips_as_enum(session: Session) -> None:
    account = helpers.make_account(session, type=AccountType.PEE)
    session.commit()
    session.expire_all()
    assert session.get(models.Account, account.id).type is AccountType.PEE  # type: ignore[union-attr]
