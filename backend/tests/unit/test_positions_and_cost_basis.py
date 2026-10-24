"""FR-005 : quantités, liquidités et prix de revient unitaire moyen, frais inclus."""

from decimal import Decimal

from finance.domain.cost_basis import compute_cost_basis
from finance.domain.entries import active_entries
from finance.domain.ledger import cash_balance, positions

from finance.domain.enums import TransactionType as T
from tests.domain_helpers import buy, d, day, deposit, make, sell


def basis(entries, on="2026-12-31", account="a1", instrument="etf"):  # type: ignore[no-untyped-def]
    return compute_cost_basis(entries, account_id=account, instrument_id=instrument, as_of=day(on))


def scenario():  # type: ignore[no-untyped-def]
    return [deposit("1000", "2026-01-05"), buy("10", "90", "2026-01-06", fees="1.99")]


def test_quickstart_scenario_cash_and_cost_basis() -> None:
    entries = scenario()
    assert cash_balance(entries, account_id="a1", as_of=day("2026-01-31")) == d("98.01")
    result = basis(entries)
    assert result.quantity == d("10")
    assert result.total_cost == d("901.99")
    assert result.unit_cost == d("90.199")
    assert not result.oversold


def test_weighted_average_of_two_purchases_includes_fees() -> None:
    entries = [buy("10", "90", "2026-01-06", fees="1.99"), buy("10", "100", "2026-02-01")]
    result = basis(entries)
    assert result.quantity == d("20")
    assert result.total_cost == d("1901.99")
    assert result.unit_cost == d("95.0995")


def test_partial_sale_keeps_the_unit_cost() -> None:
    entries = [
        buy("10", "90", "2026-01-06", fees="1.99"),
        buy("10", "100", "2026-02-01"),
        sell("5", "120", "2026-03-01", fees="2"),
    ]
    result = basis(entries)
    assert result.quantity == d("15")
    assert result.unit_cost == d("95.0995")
    assert result.total_cost == d("1426.4925")


def test_fees_on_a_sale_do_not_change_the_cost_basis() -> None:
    cheap = [buy("10", "10", "2026-01-06"), sell("4", "20", "2026-02-01", fees="0")]
    costly = [buy("10", "10", "2026-01-06"), sell("4", "20", "2026-02-01", fees="50")]
    assert basis(cheap).unit_cost == basis(costly).unit_cost == d("10")


def test_selling_everything_empties_the_position_and_a_new_purchase_restarts() -> None:
    entries = [buy("10", "90", "2026-01-06"), sell("10", "95", "2026-02-01")]
    emptied = basis(entries)
    assert (emptied.quantity, emptied.total_cost, emptied.unit_cost) == (d("0"), d("0"), None)
    entries.append(buy("4", "50", "2026-03-01"))
    restarted = basis(entries)
    assert (restarted.quantity, restarted.unit_cost) == (d("4"), d("50"))


def test_overselling_is_reported_not_hidden() -> None:
    entries = [buy("10", "90", "2026-01-06"), sell("12", "95", "2026-02-01")]
    result = basis(entries)
    assert result.quantity == d("-2")
    assert result.oversold
    assert result.unit_cost is None
    assert result.total_cost == d("0")


def test_as_of_ignores_later_operations() -> None:
    entries = scenario()
    assert basis(entries, on="2026-01-05").quantity == d("0")
    assert basis(entries, on="2026-01-06").quantity == d("10")


def test_same_day_operations_follow_their_creation_order() -> None:
    entries = [buy("10", "10", "2026-01-06"), sell("10", "11", "2026-01-06")]
    assert basis(entries).quantity == d("0")
    assert not basis(entries).oversold
    sale_first = [sell("10", "11", "2026-01-06"), buy("10", "10", "2026-01-06")]
    # Vente créée avant l'achat : elle précède et laisse un instant une position négative,
    # sans coût de revient qui survive à un solde nul.
    result = basis(sale_first)
    assert (result.quantity, result.total_cost, result.unit_cost) == (d("0"), d("0"), None)


def test_thirds_keep_the_total_exact() -> None:
    entries = [
        buy("3", "10", "2026-01-06"),
        buy("3", "10.01", "2026-01-07"),
        buy("1", "7", "2026-01-08"),
    ]
    result = basis(entries)
    assert result.total_cost == d("30") + d("30.03") + d("7")
    assert result.unit_cost is not None
    assert abs(result.unit_cost * result.quantity - result.total_cost) < Decimal("1e-40")


def test_positions_are_grouped_by_account_and_instrument() -> None:
    entries = [
        buy("10", "90", "2026-01-06"),
        buy("2", "50", "2026-01-07", instrument="fund"),
        buy("5", "90", "2026-01-08", account="a2"),
        sell("3", "95", "2026-02-01"),
    ]
    held = positions(entries, as_of=day("2026-12-31"))
    assert held == {("a1", "etf"): d("7"), ("a1", "fund"): d("2"), ("a2", "etf"): d("5")}


def test_zero_positions_are_left_out() -> None:
    entries = [buy("10", "90", "2026-01-06"), sell("10", "95", "2026-02-01")]
    assert positions(entries, as_of=day("2026-12-31")) == {}


def test_other_operations_do_not_move_quantities() -> None:
    entries = [
        buy("10", "90", "2026-01-06"),
        make(T.DIVIDEND, "2026-02-01", cash="12", instrument="etf"),
        make(T.FEE, "2026-02-02", cash="-3"),
    ]
    assert positions(entries, as_of=day("2026-12-31")) == {("a1", "etf"): d("10")}
    assert cash_balance(entries, account_id="a1", as_of=day("2026-12-31")) == d("-900") + d(
        "12"
    ) - d("3")


def test_cash_balance_respects_the_date_and_the_account() -> None:
    entries = [
        deposit("1000", "2026-01-05"),
        deposit("300", "2026-02-05"),
        deposit("77", "2026-01-05", account="a2"),
    ]
    assert cash_balance(entries, account_id="a1", as_of=day("2026-01-31")) == d("1000")
    assert cash_balance(entries, account_id="a1", as_of=day("2026-12-31")) == d("1300")
    assert cash_balance(entries, account_id="a2", as_of=day("2026-12-31")) == d("77")


def test_voided_operations_are_ignored() -> None:
    purchase = buy("10", "90", "2026-01-06")
    cancelled = make(
        T.BUY,
        "2026-01-07",
        cash="-100",
        instrument="etf",
        quantity="1",
        unit_price="100",
        voided=True,
    )
    entries = active_entries([purchase, cancelled])
    assert positions(entries, as_of=day("2026-12-31")) == {("a1", "etf"): d("10")}
    assert positions([purchase, cancelled], as_of=day("2026-12-31")) == {("a1", "etf"): d("10")}
