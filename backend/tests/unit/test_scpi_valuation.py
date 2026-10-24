"""FR-010 : SCPI valorisée au prix de retrait, prix de revient au prix de souscription."""

from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind as P
from finance.domain.enums import TransactionType as T
from finance.domain.valuation import value_account
from tests.domain_helpers import buy, d, day, deposit, instrument, make, price

SCPI = instrument("scpi", K.SCPI)


def valued(prices=(), on="2026-01-31", entries=None):  # type: ignore[no-untyped-def]
    return value_account(
        account_id="a1",
        entries=entries
        or [
            deposit("5000", "2026-01-05"),
            buy("10", "250", "2026-01-06", fees="12", instrument="scpi"),
        ],
        instruments={"scpi": SCPI},
        prices=list(prices),
        balances=[],
        as_of=day(on),
        currency="EUR",
    )


SUBSCRIPTION = price("scpi", "2026-01-05", "250", kind=P.SUBSCRIPTION)
REDEMPTION = price("scpi", "2026-01-20", "225", kind=P.REDEMPTION)


def test_cost_is_the_subscription_price_with_entry_fees() -> None:
    holding = valued([SUBSCRIPTION, REDEMPTION]).positions[0]
    assert holding.total_cost == d("2512")  # 10 x 250 + 12
    assert holding.unit_cost == d("251.2")


def test_value_is_quantity_times_the_redemption_price() -> None:
    result = valued([SUBSCRIPTION, REDEMPTION])
    holding = result.positions[0]
    assert (holding.price, holding.value) == (d("225"), d("2250"))
    assert not holding.estimated
    assert result.total == d("5000") - d("2512") + d("2250")


def test_the_initial_gap_is_visible() -> None:
    holding = valued([SUBSCRIPTION, REDEMPTION]).positions[0]
    assert holding.subscription_price == d("250")
    assert holding.value - holding.total_cost == d("-262")


def test_the_subscription_price_alone_does_not_value_the_position() -> None:
    result = valued([SUBSCRIPTION])
    holding = result.positions[0]
    assert holding.value == d("2512") and holding.estimated  # prix de revient
    assert holding.subscription_price == d("250")
    assert [w.code for w in result.warnings] == ["price_missing"]


def test_without_any_price_the_value_is_the_cost_and_is_flagged() -> None:
    result = valued([])
    holding = result.positions[0]
    assert holding.value == d("2512") and holding.estimated and holding.subscription_price is None
    assert result.estimated


def test_a_market_price_is_ignored_for_a_scpi() -> None:
    holding = valued([price("scpi", "2026-01-20", "300", kind=P.MARKET)]).positions[0]
    assert holding.value == d("2512") and holding.estimated


def test_the_latest_prices_apply_on_each_date() -> None:
    prices = [
        SUBSCRIPTION,
        REDEMPTION,
        price("scpi", "2026-03-01", "260", kind=P.SUBSCRIPTION),
        price("scpi", "2026-03-01", "230", kind=P.REDEMPTION),
    ]
    early = valued(prices, on="2026-02-15").positions[0]
    late = valued(prices, on="2026-03-15").positions[0]
    assert (early.price, early.subscription_price) == (d("225"), d("250"))
    assert (late.price, late.subscription_price) == (d("230"), d("260"))
    assert late.value == d("2300")


def test_a_redemption_price_older_than_a_quarter_is_estimated() -> None:
    result = valued([REDEMPTION], on="2026-05-31")  # 131 jours
    assert result.positions[0].estimated
    assert [w.code for w in result.warnings] == ["price_stale"]


def test_distributions_are_cash_operations_not_a_change_of_position() -> None:
    entries = [
        deposit("5000", "2026-01-05"),
        buy("10", "250", "2026-01-06", fees="12", instrument="scpi"),
        make(T.DISTRIBUTION, "2026-01-25", cash="31.50", instrument="scpi"),
    ]
    result = valued([SUBSCRIPTION, REDEMPTION], entries=entries)
    holding = result.positions[0]
    assert holding.quantity == d("10") and holding.total_cost == d("2512")
    assert result.cash == d("5000") - d("2512") + d("31.50")
    assert result.total == result.cash + d("2250")


def test_fractional_shares() -> None:
    entries = [deposit("5000", "2026-01-05"), buy("3.5", "250", "2026-01-06", instrument="scpi")]
    holding = valued([REDEMPTION], entries=entries).positions[0]
    assert holding.value == d("787.5") and holding.total_cost == d("875")
