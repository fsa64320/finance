"""Service du tableau de bord : synthèse, série et répartition sur la base chiffrée."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from finance.domain.allocation import AssetClass
from finance.domain.enums import AccountType as A
from finance.domain.enums import InstrumentKind as K
from finance.services import (
    accounts,
    balances,
    dashboard,
    instruments,
    rates,
    transactions,
    transfers,
)
from finance.services.errors import ValidationFailed
from tests.integration.test_services_us1 import buy, d, deposit, new_account, new_etf

TODAY = date(2026, 3, 31)


def quickstart(session: Session):  # type: ignore[no-untyped-def]
    """PEA (1 000 € dont 901,99 € d'ETF), Livret A (2 500 €) et assurance-vie (5 000 €).

    Un taux de 0 % garde des soldes ronds ; les intérêts estimés ont leurs propres tests.
    """
    rates.add_livret_a_rate(session, effective_from=date(2026, 1, 1), value=d("0"))
    pea = new_account(session)
    etf = new_etf(session)
    deposit(session, pea, "1000")
    buy(session, pea, etf, "10")
    livret = new_account(session, "Livret A", A.LIVRET_A)
    deposit(session, livret, "3000", "2026-01-03")
    transactions.create_transaction(
        session,
        transactions.TransactionData(
            account_id=livret.id,
            type=transactions.T.WITHDRAWAL,
            trade_date=date(2026, 1, 10),
            currency="EUR",
            amount=d("500"),
        ),
    )
    vie = accounts.create_account(
        session, type=A.ASSURANCE_VIE, name="Assurance-vie", opened_on=date(2025, 6, 1)
    )
    fund = instruments.create_instrument(
        session, kind=K.EURO_FUND, name="Fonds en euros", currency="EUR"
    )
    balances.declare_balance(
        session,
        balances.BalanceData(
            account_id=vie.id,
            instrument_id=fund.id,
            balance_date=date(2026, 1, 1),
            amount=d("5000"),
            currency="EUR",
        ),
    )
    return pea, livret, vie, etf, fund


def test_summary_adds_up_the_open_accounts(session: Session) -> None:
    quickstart(session)
    summary = dashboard.summary(session, TODAY)
    assert summary.currency == "EUR"
    assert summary.net_worth == d("8500")
    assert summary.estimated  # l'ETF n'a pas de prix
    assert summary.as_of == TODAY


def test_summary_notices_explain_the_estimates(session: Session) -> None:
    _, _, _, etf, _ = quickstart(session)
    notices = dashboard.summary(session, TODAY).notices
    assert [(n.kind, n.instrument_id) for n in notices] == [("stale_price", etf.id)]
    assert notices[0].account_id is not None
    assert "prix" in notices[0].message.lower()


def test_summary_flags_a_missing_declared_balance(session: Session) -> None:
    vie = accounts.create_account(
        session, type=A.ASSURANCE_VIE, name="AV", opened_on=date(2025, 6, 1)
    )
    fund = instruments.create_instrument(
        session, kind=K.EURO_FUND, name="Fonds en euros", currency="EUR"
    )
    transactions.create_transaction(
        session,
        transactions.TransactionData(
            account_id=vie.id,
            type=transactions.T.BUY,
            trade_date=date(2026, 1, 10),
            currency="EUR",
            instrument_id=fund.id,
            quantity=d("1000"),
            unit_price=d("1"),
        ),
    )
    kinds = [n.kind for n in dashboard.summary(session, TODAY).notices]
    assert kinds == ["missing_balance"]


def test_empty_instance_has_a_zero_patrimony(session: Session) -> None:
    summary = dashboard.summary(session, TODAY)
    assert (summary.net_worth, summary.estimated, summary.notices) == (d("0"), False, ())


def test_closed_account_leaves_the_summary(session: Session) -> None:
    _, livret, _, _, _ = quickstart(session)
    accounts.update_account(session, livret.id, {"closed_on": date(2026, 2, 1)})
    assert dashboard.summary(session, TODAY).net_worth == d("6000")
    assert dashboard.summary(session, date(2026, 1, 31)).net_worth == d("8500")


def test_transfers_do_not_change_the_patrimony(session: Session) -> None:
    pea, livret, _, _, _ = quickstart(session)
    before = dashboard.summary(session, TODAY).net_worth
    transfers.create_transfer(
        session,
        transfers.TransferData(
            from_account_id=pea.id,
            to_account_id=livret.id,
            trade_date=date(2026, 3, 1),
            amount=d("500"),
            currency="EUR",
        ),
    )
    assert dashboard.summary(session, TODAY).net_worth == before


def test_allocation_groups_by_asset_class(session: Session) -> None:
    quickstart(session)
    result = dashboard.allocation(session, TODAY)
    slices = {s.asset_class: s for s in result.slices}
    assert slices[AssetClass.EQUITIES_ETF].value == d("901.99")
    assert slices[AssetClass.CASH].value == d("98.01") + d("2500")
    assert slices[AssetClass.EURO_FUNDS].value == d("5000")
    assert sum(s.weight_percent for s in result.slices) == Decimal(100)


def test_series_for_a_year_is_daily_and_ends_on_the_last_day(session: Session) -> None:
    quickstart(session)
    result = dashboard.series(session, "1y", TODAY)
    assert result.points[-1].date == TODAY
    assert result.points[-1].value == d("8500")
    assert len(result.points) == 366
    assert result.currency == "EUR"


def test_series_starts_at_the_first_activity_for_the_whole_history(session: Session) -> None:
    quickstart(session)
    result = dashboard.series(session, "all", TODAY)
    assert result.points[0].date == date(2025, 6, 1)  # ouverture de l'assurance-vie
    assert result.points[-1].date == TODAY


def test_series_is_empty_without_any_account(session: Session) -> None:
    assert dashboard.series(session, "1y", TODAY).points == []


def test_unknown_period_is_a_validation_error(session: Session) -> None:
    with pytest.raises(ValidationFailed) as raised:
        dashboard.series(session, "7y", TODAY)
    assert raised.value.details[0].field == "period"


# ------------------------------------------------------------------------ cache


def test_results_are_cached_until_the_data_changes(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    quickstart(session)
    session.commit()
    calls = 0
    original = dashboard.compute_net_worth

    def counting(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(**kwargs)

    monkeypatch.setattr(dashboard, "compute_net_worth", counting)
    first = dashboard.summary(session, TODAY)
    second = dashboard.summary(session, TODAY)
    assert first == second and calls == 1


def test_a_write_invalidates_the_cache(session: Session) -> None:
    pea, *_ = quickstart(session)
    session.commit()
    before = dashboard.summary(session, TODAY).net_worth
    deposit(session, pea, "100", "2026-02-01")
    session.commit()
    assert dashboard.summary(session, TODAY).net_worth == before + d("100")


def test_a_rolled_back_write_does_not_invalidate_a_wrong_value(session: Session) -> None:
    pea, *_ = quickstart(session)
    session.commit()
    before = dashboard.summary(session, TODAY).net_worth
    deposit(session, pea, "100", "2026-02-01")
    session.rollback()
    assert dashboard.summary(session, TODAY).net_worth == before


def test_cache_is_reconstructible_identically(session: Session) -> None:
    quickstart(session)
    session.commit()
    cached = dashboard.series(session, "all", TODAY)
    dashboard.clear_cache()
    assert dashboard.series(session, "all", TODAY) == cached
