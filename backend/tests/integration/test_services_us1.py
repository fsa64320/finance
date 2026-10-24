"""Services de l'histoire US1 sur la base chiffrée : comptes, actifs, opérations, virements."""

from datetime import date
from decimal import Decimal

import pytest
from finance.services.errors import ConflictError, NotFoundError, ValidationFailed
from finance.services.transactions import TransactionData
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import AccountType as A
from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceMode
from finance.domain.enums import TransactionType as T
from finance.services import accounts, balances, instruments, transactions, transfers


def d(value: str) -> Decimal:
    return Decimal(value)


def new_account(
    session: Session, name: str = "PEA", kind: A = A.PEA, **kw: object
) -> models.Account:
    return accounts.create_account(
        session,
        type=kind,
        name=name,
        opened_on=date(2026, 1, 2),
        **kw,  # type: ignore[arg-type]
    )


def new_etf(session: Session, isin: str | None = "IE00B4L5Y983") -> models.Instrument:
    return instruments.create_instrument(
        session, kind=K.ETF, name=f"ETF {isin}", currency="EUR", isin=isin
    )


def deposit(session: Session, account: models.Account, amount: str, on: str = "2026-01-05") -> None:
    transactions.create_transaction(
        session,
        TransactionData(
            account_id=account.id,
            type=T.DEPOSIT,
            trade_date=date.fromisoformat(on),
            currency="EUR",
            amount=d(amount),
        ),
    )


def buy(
    session: Session,
    account: models.Account,
    etf: models.Instrument,
    quantity: str,
    on: str = "2026-01-06",
) -> transactions.TransactionOutcome:
    return transactions.create_transaction(
        session,
        TransactionData(
            account_id=account.id,
            type=T.BUY,
            trade_date=date.fromisoformat(on),
            currency="EUR",
            instrument_id=etf.id,
            quantity=d(quantity),
            unit_price=d("90"),
            fees=d("1.99"),
        ),
    )


# ------------------------------------------------------------------ comptes


def test_account_defaults_follow_the_type(session: Session) -> None:
    pea = new_account(session)
    livret = new_account(session, "Livret A", A.LIVRET_A)
    pee = new_account(session, "PEE", A.PEE)
    cto = new_account(session, "CTO", A.CTO)
    assert pea.currency == "EUR"
    assert pea.settings == {"deposit_cap": "150000"}
    assert livret.settings == {"deposit_cap": "22950"}
    assert pee.settings == {"lock_years": 5}
    assert cto.settings == {}


def test_explicit_settings_override_the_defaults(session: Session) -> None:
    pea = new_account(session, settings={"deposit_cap": "25000"})
    assert pea.settings["deposit_cap"] == "25000"


@pytest.mark.parametrize("cap", ["0", "-5", "abc", 100])
def test_invalid_cap_is_refused(session: Session, cap: object) -> None:
    with pytest.raises(ValidationFailed) as raised:
        new_account(session, settings={"deposit_cap": cap})
    assert raised.value.details[0].field == "settings.deposit_cap"


def test_open_account_names_are_unique(session: Session) -> None:
    new_account(session, "PEA")
    with pytest.raises(ConflictError):
        new_account(session, "PEA", A.CTO)


def test_a_closed_account_frees_its_name(session: Session) -> None:
    first = new_account(session, "PEA")
    accounts.update_account(session, first.id, {"closed_on": date(2026, 6, 30)})
    new_account(session, "PEA")


def test_closing_before_opening_is_refused(session: Session) -> None:
    pea = new_account(session)
    with pytest.raises(ValidationFailed) as raised:
        accounts.update_account(session, pea.id, {"closed_on": date(2025, 12, 31)})
    assert raised.value.details[0].field == "closed_on"


def test_account_can_be_renamed_and_reopened(session: Session) -> None:
    pea = new_account(session)
    accounts.update_account(session, pea.id, {"name": "PEA Courtier B", "institution": "B"})
    accounts.update_account(session, pea.id, {"closed_on": date(2026, 6, 30)})
    reopened = accounts.update_account(session, pea.id, {"closed_on": None})
    assert (reopened.name, reopened.institution, reopened.closed_on) == (
        "PEA Courtier B",
        "B",
        None,
    )


def test_renaming_to_an_open_name_is_a_conflict(session: Session) -> None:
    new_account(session, "PEA")
    other = new_account(session, "CTO", A.CTO)
    with pytest.raises(ConflictError):
        accounts.update_account(session, other.id, {"name": "PEA"})


def test_unknown_account_is_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError):
        accounts.get_account(session, "inconnu")


def test_closed_accounts_are_listed_only_on_request(session: Session) -> None:
    keep = new_account(session, "PEA")
    gone = new_account(session, "CTO", A.CTO)
    accounts.update_account(session, gone.id, {"closed_on": date(2026, 6, 30)})
    assert [a.id for a in accounts.list_accounts(session)] == [keep.id]
    assert {a.id for a in accounts.list_accounts(session, include_closed=True)} == {
        keep.id,
        gone.id,
    }


def test_overview_of_a_pea_matches_the_quickstart(session: Session) -> None:
    pea = new_account(session)
    etf = new_etf(session)
    deposit(session, pea, "1000")
    buy(session, pea, etf, "10")
    overview = accounts.account_overview(session, pea, date(2026, 1, 31))
    assert overview.cash == d("98.01")
    assert overview.value.total == d("1000")
    assert overview.value.estimated
    assert overview.deposit_cap_usage is not None
    assert (overview.deposit_cap_usage.used, overview.deposit_cap_usage.cap) == (
        d("1000"),
        d("150000"),
    )
    assert overview.locked_amount is None


def test_overview_of_a_pee_reports_locked_amounts(session: Session) -> None:
    pee = new_account(session, "PEE", A.PEE)
    transactions.create_transaction(
        session,
        TransactionData(
            account_id=pee.id,
            type=T.DEPOSIT,
            trade_date=date(2026, 1, 5),
            currency="EUR",
            amount=d("1000"),
            unlock_date=date(2031, 1, 5),
        ),
    )
    overview = accounts.account_overview(session, pee, date(2026, 6, 1))
    assert overview.locked_amount == d("1000")
    assert overview.deposit_cap_usage is None


def test_overview_of_a_livret_a_uses_the_balance_against_the_cap(session: Session) -> None:
    livret = new_account(session, "Livret A", A.LIVRET_A)
    deposit(session, livret, "3000")
    usage = accounts.account_overview(session, livret, date(2026, 6, 1)).deposit_cap_usage
    assert usage is not None
    assert (usage.used, usage.cap, usage.remaining) == (d("3000"), d("22950"), d("19950"))


# -------------------------------------------------------------------- actifs


def test_instrument_defaults_and_isin_normalisation(session: Session) -> None:
    etf = new_etf(session, "  ie00b4l5y983 ")
    assert etf.isin == "IE00B4L5Y983"
    assert etf.price_mode is PriceMode.AUTO
    for kind in (K.SCPI, K.FCPE, K.EURO_FUND, K.CASH):
        created = instruments.create_instrument(session, kind=kind, name=str(kind), currency="EUR")
        assert created.price_mode is PriceMode.MANUAL


def test_invalid_isin_is_refused(session: Session) -> None:
    with pytest.raises(ValidationFailed) as raised:
        new_etf(session, "IE00B4L5Y984")
    assert raised.value.details[0].field == "isin"


def test_duplicate_isin_is_a_conflict(session: Session) -> None:
    new_etf(session)
    with pytest.raises(ConflictError):
        new_etf(session)


def test_instrument_patch_and_unknown_instrument(session: Session) -> None:
    etf = new_etf(session)
    patched = instruments.update_instrument(
        session,
        etf.id,
        {"name": "ETF Monde", "price_ticker": "CW8.PA", "price_mode": PriceMode.MANUAL},
    )
    assert (patched.name, patched.price_ticker, patched.price_mode) == (
        "ETF Monde",
        "CW8.PA",
        PriceMode.MANUAL,
    )
    assert (
        instruments.update_instrument(session, etf.id, {"price_ticker": None}).price_ticker is None
    )
    with pytest.raises(NotFoundError):
        instruments.update_instrument(session, "inconnu", {"name": "x"})


# ---------------------------------------------------------------- opérations


def test_create_stores_version_one_with_the_computed_cash_effect(session: Session) -> None:
    pea = new_account(session)
    etf = new_etf(session)
    deposit(session, pea, "1000")
    outcome = buy(session, pea, etf, "10")
    assert outcome.version.version == 1
    assert outcome.version.cash_amount == d("-901.99")
    assert outcome.warnings == []


def test_update_adds_a_version_and_keeps_the_old_one(session: Session) -> None:
    pea = new_account(session)
    etf = new_etf(session)
    deposit(session, pea, "2000")
    created = buy(session, pea, etf, "10")
    updated = transactions.update_transaction(
        session,
        created.version.transaction_id,
        TransactionData(
            account_id=pea.id,
            type=T.BUY,
            trade_date=date(2026, 1, 6),
            currency="EUR",
            instrument_id=etf.id,
            quantity=d("12"),
            unit_price=d("90"),
            fees=d("1.99"),
        ),
    )
    assert updated.version.version == 2 and updated.version.cash_amount == d("-1081.99")
    current, versions = transactions.get_transaction(session, created.version.transaction_id)
    assert current.version == 2
    assert [(v.version, v.quantity) for v in versions] == [(1, d("10")), (2, d("12"))]
    count = session.scalar(select(func.count()).select_from(models.TransactionVersion))
    assert count == 3  # versement + 2 versions de l'achat


def test_void_adds_a_voided_version_and_is_idempotent(session: Session) -> None:
    pea = new_account(session)
    deposit(session, pea, "100")
    transaction_id = session.scalars(select(models.Transaction.id)).one()
    cancelled = transactions.void_transaction(session, transaction_id)
    assert cancelled.version.version == 2 and cancelled.version.voided
    again = transactions.void_transaction(session, transaction_id)
    assert again.version.version == 2


def test_list_hides_voided_and_old_versions(session: Session) -> None:
    pea = new_account(session)
    deposit(session, pea, "100", "2026-01-05")
    deposit(session, pea, "200", "2026-01-06")
    first_id = session.scalars(
        select(models.Transaction.id).order_by(models.Transaction.created_at)
    ).first()
    assert first_id is not None
    transactions.void_transaction(session, first_id)
    visible = transactions.list_transactions(session)
    assert [row.cash_amount for row in visible.items] == [d("200")]
    everything = transactions.list_transactions(session, include_voided=True)
    assert len(everything.items) == 2


def test_list_filters_and_pagination(session: Session) -> None:
    pea = new_account(session)
    cto = new_account(session, "CTO", A.CTO)
    for day in range(5, 10):
        deposit(session, pea, str(day), f"2026-01-0{day}")
    deposit(session, cto, "999", "2026-01-05")
    only_pea = transactions.list_transactions(session, account_id=pea.id)
    assert len(only_pea.items) == 5
    window = transactions.list_transactions(
        session, account_id=pea.id, date_from=date(2026, 1, 6), date_to=date(2026, 1, 8)
    )
    assert [row.cash_amount for row in window.items] == [d("8"), d("7"), d("6")]
    first = transactions.list_transactions(session, account_id=pea.id, limit=2)
    assert [row.cash_amount for row in first.items] == [d("9"), d("8")]
    assert first.next_cursor is not None
    second = transactions.list_transactions(
        session, account_id=pea.id, limit=2, cursor=first.next_cursor
    )
    assert [row.cash_amount for row in second.items] == [d("7"), d("6")]
    last = transactions.list_transactions(
        session, account_id=pea.id, limit=2, cursor=second.next_cursor
    )
    assert [row.cash_amount for row in last.items] == [d("5")]
    assert last.next_cursor is None


def test_invalid_cursor_is_refused(session: Session) -> None:
    with pytest.raises(ValidationFailed):
        transactions.list_transactions(session, cursor="pas-un-curseur")


def test_rule_violations_are_reported_together(session: Session) -> None:
    livret = new_account(session, "Livret A", A.LIVRET_A)
    etf = new_etf(session)
    with pytest.raises(ValidationFailed) as raised:
        transactions.create_transaction(
            session,
            TransactionData(
                account_id=livret.id,
                type=T.BUY,
                trade_date=date(2025, 1, 1),
                currency="EUR",
                instrument_id=etf.id,
                quantity=d("0"),
                unit_price=d("90"),
            ),
        )
    fields = {detail.field for detail in raised.value.details}
    assert {"type", "trade_date", "quantity"} <= fields
    assert session.scalar(select(func.count()).select_from(models.Transaction)) == 0


def test_unknown_account_or_instrument_is_refused(session: Session) -> None:
    pea = new_account(session)
    with pytest.raises(ValidationFailed) as raised:
        transactions.create_transaction(
            session,
            TransactionData(
                account_id="inconnu",
                type=T.DEPOSIT,
                trade_date=date(2026, 1, 5),
                currency="EUR",
                amount=d("1"),
            ),
        )
    assert raised.value.details[0].field == "account_id"
    with pytest.raises(ValidationFailed) as raised:
        transactions.create_transaction(
            session,
            TransactionData(
                account_id=pea.id,
                type=T.BUY,
                trade_date=date(2026, 1, 6),
                currency="EUR",
                instrument_id="inconnu",
                quantity=d("1"),
                unit_price=d("1"),
            ),
        )
    assert raised.value.details[0].field == "instrument_id"


def test_overselling_and_negative_cash_are_warnings_not_errors(session: Session) -> None:
    pea = new_account(session)
    etf = new_etf(session)
    outcome = buy(session, pea, etf, "10")  # sans versement : liquidités négatives
    assert any("liquidités" in warning for warning in outcome.warnings)
    sale = transactions.create_transaction(
        session,
        TransactionData(
            account_id=pea.id,
            type=T.SELL,
            trade_date=date(2026, 2, 1),
            currency="EUR",
            instrument_id=etf.id,
            quantity=d("12"),
            unit_price=d("95"),
        ),
    )
    assert any("quantité détenue" in warning for warning in sale.warnings)


def test_update_cannot_move_a_transaction_to_another_account(session: Session) -> None:
    pea = new_account(session)
    cto = new_account(session, "CTO", A.CTO)
    deposit(session, pea, "100")
    transaction_id = session.scalars(select(models.Transaction.id)).one()
    with pytest.raises(ValidationFailed) as raised:
        transactions.update_transaction(
            session,
            transaction_id,
            TransactionData(
                account_id=cto.id,
                type=T.DEPOSIT,
                trade_date=date(2026, 1, 5),
                currency="EUR",
                amount=d("100"),
            ),
        )
    assert raised.value.details[0].field == "account_id"


def test_journal_rows_cannot_be_modified_through_the_orm(session: Session) -> None:
    from finance.db.append_only import AppendOnlyError

    pea = new_account(session)
    deposit(session, pea, "100")
    session.flush()
    row = session.scalars(select(models.TransactionVersion)).one()
    row.label = "modifié"
    with pytest.raises(AppendOnlyError):
        session.flush()
    session.rollback()


# ------------------------------------------------------------------ virements


def new_transfer(
    session: Session, source: models.Account, target: models.Account, amount: str = "500"
) -> transfers.TransferOutcome:
    return transfers.create_transfer(
        session,
        transfers.TransferData(
            from_account_id=source.id,
            to_account_id=target.id,
            trade_date=date(2026, 3, 1),
            amount=d(amount),
            currency="EUR",
        ),
    )


def test_transfer_creates_two_linked_legs(session: Session) -> None:
    pea = new_account(session)
    livret = new_account(session, "Livret A", A.LIVRET_A)
    deposit(session, pea, "2000")
    deposit(session, livret, "3000")
    outcome = new_transfer(session, pea, livret)
    assert (
        outcome.out.version.transfer_group_id
        == outcome.group_id
        == outcome.into.version.transfer_group_id
    )
    assert (outcome.out.version.type, outcome.into.version.type) == (T.TRANSFER_OUT, T.TRANSFER_IN)
    assert (outcome.out.version.cash_amount, outcome.into.version.cash_amount) == (
        d("-500"),
        d("500"),
    )
    assert accounts.account_overview(session, pea, date(2026, 12, 31)).cash == d("1500")
    assert accounts.account_overview(session, livret, date(2026, 12, 31)).cash == d("3500")


def test_transfer_refuses_the_same_account_and_unknown_accounts(session: Session) -> None:
    pea = new_account(session)
    with pytest.raises(ValidationFailed):
        new_transfer(session, pea, pea)
    with pytest.raises(ValidationFailed) as raised:
        transfers.create_transfer(
            session,
            transfers.TransferData(
                from_account_id=pea.id,
                to_account_id="inconnu",
                trade_date=date(2026, 3, 1),
                amount=d("5"),
                currency="EUR",
            ),
        )
    assert raised.value.details[0].field == "to_account_id"


def test_transfer_currency_must_match_both_accounts(session: Session) -> None:
    pea = new_account(session)
    usd = new_account(session, "CTO USD", A.CTO, currency="USD")
    with pytest.raises(ValidationFailed) as raised:
        new_transfer(session, pea, usd)
    assert raised.value.details[0].field == "currency"


def test_transfer_date_cannot_precede_either_opening(session: Session) -> None:
    pea = new_account(session)
    late = accounts.create_account(session, type=A.CTO, name="CTO", opened_on=date(2026, 6, 1))
    with pytest.raises(ValidationFailed) as raised:
        new_transfer(session, pea, late)
    assert raised.value.details[0].field == "trade_date"


def test_voiding_a_leg_voids_both(session: Session) -> None:
    pea = new_account(session)
    livret = new_account(session, "Livret A", A.LIVRET_A)
    outcome = new_transfer(session, pea, livret)
    cancelled = transactions.void_transaction(session, outcome.out.version.transaction_id)
    assert cancelled.version.voided
    for leg in (outcome.out, outcome.into):
        current, _ = transactions.get_transaction(session, leg.version.transaction_id)
        assert current.voided and current.version == 2
    assert accounts.account_overview(session, livret, date(2026, 12, 31)).cash == d("0")


def test_updating_a_transfer_changes_both_legs(session: Session) -> None:
    pea = new_account(session)
    livret = new_account(session, "Livret A", A.LIVRET_A)
    outcome = new_transfer(session, pea, livret)
    updated = transfers.update_transfer(
        session, outcome.group_id, amount=d("750"), trade_date=date(2026, 3, 10)
    )
    assert (updated.out.version.cash_amount, updated.into.version.cash_amount) == (
        d("-750"),
        d("750"),
    )
    assert updated.out.version.version == updated.into.version.version == 2
    assert updated.out.version.trade_date == updated.into.version.trade_date == date(2026, 3, 10)


def test_a_transfer_leg_cannot_be_edited_alone(session: Session) -> None:
    pea = new_account(session)
    livret = new_account(session, "Livret A", A.LIVRET_A)
    outcome = new_transfer(session, pea, livret)
    with pytest.raises(ValidationFailed):
        transactions.update_transaction(
            session,
            outcome.out.version.transaction_id,
            TransactionData(
                account_id=pea.id,
                type=T.DEPOSIT,
                trade_date=date(2026, 3, 1),
                currency="EUR",
                amount=d("1"),
            ),
        )


def test_unknown_transfer_group_is_not_found(session: Session) -> None:
    with pytest.raises(NotFoundError):
        transfers.update_transfer(session, "inconnu", amount=d("1"))
    with pytest.raises(NotFoundError):
        transfers.void_transfer(session, "inconnu")


# ---------------------------------------------------------------------- soldes


def test_declared_balance_for_a_euro_fund(session: Session) -> None:
    vie = new_account(session, "AV", A.ASSURANCE_VIE)
    fund = instruments.create_instrument(
        session, kind=K.EURO_FUND, name="Fonds en euros", currency="EUR"
    )
    row = balances.declare_balance(
        session,
        balances.BalanceData(
            account_id=vie.id,
            instrument_id=fund.id,
            balance_date=date(2026, 1, 1),
            amount=d("5000"),
            currency="EUR",
        ),
    )
    assert row.amount == d("5000")
    overview = accounts.account_overview(session, vie, date(2026, 1, 31))
    assert overview.value.total == d("5000")


def test_declared_balance_rules(session: Session) -> None:
    vie = new_account(session, "AV", A.ASSURANCE_VIE)
    etf = new_etf(session)
    fund = instruments.create_instrument(
        session, kind=K.EURO_FUND, name="Fonds en euros", currency="EUR"
    )

    def declare(**changes: object) -> models.DeclaredBalance:
        values: dict[str, object] = {
            "account_id": vie.id,
            "instrument_id": fund.id,
            "balance_date": date(2026, 1, 1),
            "amount": d("5000"),
            "currency": "EUR",
        }
        values.update(changes)
        return balances.declare_balance(session, balances.BalanceData(**values))  # type: ignore[arg-type]

    with pytest.raises(ValidationFailed) as raised:
        declare(instrument_id=etf.id)
    assert raised.value.details[0].field == "instrument_id"
    with pytest.raises(ValidationFailed) as raised:
        declare(amount=d("-1"))
    assert raised.value.details[0].field == "amount"
    with pytest.raises(ValidationFailed) as raised:
        declare(account_id="inconnu")
    assert raised.value.details[0].field == "account_id"
    with pytest.raises(ValidationFailed) as raised:
        declare(instrument_id="inconnu")
    assert raised.value.details[0].field == "instrument_id"
    assert declare(amount=d("0")).amount == d("0")


def test_a_corrected_declaration_adds_a_row(session: Session) -> None:
    vie = new_account(session, "AV", A.ASSURANCE_VIE)
    fund = instruments.create_instrument(
        session, kind=K.EURO_FUND, name="Fonds en euros", currency="EUR"
    )
    for amount in ("4000", "5000"):
        balances.declare_balance(
            session,
            balances.BalanceData(
                account_id=vie.id,
                instrument_id=fund.id,
                balance_date=date(2026, 1, 1),
                amount=d(amount),
                currency="EUR",
            ),
        )
    assert session.scalar(select(func.count()).select_from(models.DeclaredBalance)) == 2
    assert accounts.account_overview(session, vie, date(2026, 1, 31)).value.total == d("5000")
