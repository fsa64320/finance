"""FR-005, FR-025 : valeur des positions et du compte, avec repli sur le prix de revient."""

from decimal import Decimal

import pytest

from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind as P
from finance.domain.enums import TransactionType as T
from finance.domain.valuation import AccountValue, PositionValue, value_account
from tests.domain_helpers import buy, d, day, deposit, instrument, make, price, sell

ETF = instrument("etf", K.ETF)


def value(entries, prices=(), instruments=None, on="2026-01-31") -> AccountValue:  # type: ignore[no-untyped-def]
    return value_account(
        account_id="a1",
        entries=entries,
        instruments={"etf": ETF} if instruments is None else instruments,
        prices=list(prices),
        balances=[],
        as_of=day(on),
        currency="EUR",
    )


def position(result: AccountValue, identifier: str = "etf") -> PositionValue:
    return next(p for p in result.positions if p.instrument_id == identifier)


def scenario():  # type: ignore[no-untyped-def]
    return [deposit("1000", "2026-01-05"), buy("10", "90", "2026-01-06", fees="1.99")]


def test_priced_position_is_quantity_times_the_latest_price() -> None:
    result = value(scenario(), [price("etf", "2026-01-20", "90.2")])
    holding = position(result)
    assert (holding.quantity, holding.price, holding.value) == (d("10"), d("90.2"), d("902"))
    assert holding.price_date == day("2026-01-20")
    assert not holding.estimated
    assert holding.unit_cost == d("90.199") and holding.total_cost == d("901.99")


def test_account_total_adds_cash_and_positions() -> None:
    result = value(scenario(), [price("etf", "2026-01-20", "90.2")])
    assert result.cash == d("98.01")
    assert result.total == d("1000.01")
    assert not result.estimated and result.warnings == ()


def test_latest_price_not_after_the_date_is_used() -> None:
    prices = [
        price("etf", "2026-01-10", "90"),
        price("etf", "2026-01-25", "95"),
        price("etf", "2026-02-10", "99"),
    ]
    assert position(value(scenario(), prices)).price == d("95")
    assert position(value(scenario(), prices, on="2026-01-12")).price == d("90")


def test_the_most_recent_entry_wins_on_the_same_date() -> None:
    prices = [
        price("etf", "2026-01-25", "95", recorded=1),
        price("etf", "2026-01-25", "96", recorded=5),
        price("etf", "2026-01-25", "94", recorded=3),
    ]
    assert position(value(scenario(), prices)).price == d("96")


def test_without_a_price_the_position_is_valued_at_cost_and_flagged() -> None:
    result = value(scenario())
    holding = position(result)
    assert holding.price is None
    assert holding.value == d("901.99")
    assert holding.estimated
    assert result.estimated
    assert [w.code for w in result.warnings] == ["price_missing"]


def test_a_price_of_the_wrong_kind_is_ignored() -> None:
    prices = [price("etf", "2026-01-20", "50", kind=P.SUBSCRIPTION)]
    assert position(value(scenario(), prices)).price is None


@pytest.mark.parametrize(
    ("kind", "price_kind"),
    [
        (K.EQUITY, P.MARKET),
        (K.ETF, P.MARKET),
        (K.FUND, P.NAV),
        (K.FCPE, P.NAV),
        (K.SCPI, P.REDEMPTION),
    ],
)
def test_each_kind_reads_its_own_price_kind(kind: K, price_kind: P) -> None:
    instruments = {"x": instrument("x", kind)}
    entries = [deposit("5000", "2026-01-02"), buy("10", "100", "2026-01-03", instrument="x")]
    result = value(entries, [price("x", "2026-01-20", "110", kind=price_kind)], instruments)
    assert position(result, "x").value == d("1100")


def test_closed_positions_are_not_listed() -> None:
    entries = [*scenario(), sell("10", "95", "2026-01-15")]
    assert value(entries).positions == ()


def test_positions_after_the_date_are_not_counted() -> None:
    assert value(scenario(), on="2026-01-05").positions == ()
    assert value(scenario(), on="2026-01-05").total == d("1000")


def test_a_negative_position_is_reported() -> None:
    entries = [buy("10", "90", "2026-01-06"), sell("12", "95", "2026-02-01")]
    result = value(entries, [price("etf", "2026-02-02", "95")], on="2026-02-10")
    assert "negative_position" in {w.code for w in result.warnings}
    assert result.estimated


def test_price_in_another_currency_cannot_be_converted_yet() -> None:
    prices = [price("etf", "2026-01-20", "100", currency="USD")]
    result = value(scenario(), prices)
    holding = position(result)
    assert holding.value is None
    assert "non_convertible" in {w.code for w in result.warnings}
    assert result.total == d("98.01")
    assert result.estimated


def test_unknown_instrument_is_an_error() -> None:
    with pytest.raises(KeyError, match="etf"):
        value(scenario(), instruments={})


def test_other_accounts_are_ignored() -> None:
    entries = [*scenario(), buy("99", "1", "2026-01-07", account="autre")]
    assert position(value(entries)).quantity == d("10")


def test_dividends_add_cash_without_changing_positions() -> None:
    entries = [*scenario(), make(T.DIVIDEND, "2026-01-15", cash="12", instrument="etf")]
    result = value(entries, [price("etf", "2026-01-20", "90.2")])
    assert result.cash == d("110.01")
    assert position(result).quantity == d("10")


def test_result_is_exact_decimal() -> None:
    result = value(scenario(), [price("etf", "2026-01-20", "0.1")])
    assert isinstance(result.total, Decimal)
    assert result.total == d("98.01") + d("1.0")


def test_cash_instruments_are_not_positions() -> None:
    cash = instrument("cash", K.CASH)
    entries = [deposit("100", "2026-01-02"), buy("1", "1", "2026-01-03", instrument="cash")]
    result = value(entries, instruments={"cash": cash})
    assert result.positions == ()
    assert result.cash == d("99")
