"""FR-013, FR-025 : prix applicable à une date, et prix ancien signalé comme estimé."""

from datetime import timedelta

import pytest
from finance.domain.prices import STALE_AFTER_DAYS, is_stale, select_price

from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind as P
from finance.domain.valuation import value_account
from tests.domain_helpers import buy, d, day, deposit, instrument, price

PRICES = [
    price("etf", "2026-01-10", "90"),
    price("etf", "2026-01-25", "95"),
    price("etf", "2026-02-10", "99"),
    price("other", "2026-01-26", "7"),
    price("etf", "2026-01-26", "50", kind=P.NAV),
]


def test_the_latest_price_not_after_the_date_wins() -> None:
    chosen = select_price(PRICES, "etf", P.MARKET, day("2026-01-31"))
    assert chosen is not None and chosen.value == d("95")


def test_a_price_on_the_date_itself_counts() -> None:
    chosen = select_price(PRICES, "etf", P.MARKET, day("2026-01-25"))
    assert chosen is not None and chosen.value == d("95")


def test_the_date_before_the_first_price_has_none() -> None:
    assert select_price(PRICES, "etf", P.MARKET, day("2026-01-09")) is None


def test_other_instruments_and_kinds_are_ignored() -> None:
    assert select_price(PRICES, "etf", P.REDEMPTION, day("2026-03-01")) is None
    chosen = select_price(PRICES, "etf", P.NAV, day("2026-03-01"))
    assert chosen is not None and chosen.value == d("50")


def test_on_the_same_date_the_latest_entry_wins() -> None:
    prices = [
        price("etf", "2026-01-10", "90", recorded=5),
        price("etf", "2026-01-10", "91", recorded=9),
        price("etf", "2026-01-10", "89", recorded=1),
    ]
    chosen = select_price(prices, "etf", P.MARKET, day("2026-01-10"))
    assert chosen is not None and chosen.value == d("91")


def test_an_exact_tie_keeps_the_first_received() -> None:
    prices = [price("etf", "2026-01-10", "90"), price("etf", "2026-01-10", "91")]
    chosen = select_price(prices, "etf", P.MARKET, day("2026-01-10"))
    assert chosen is not None and chosen.value == d("90")


@pytest.mark.parametrize("kind", list(P))
def test_staleness_thresholds_are_inclusive_of_the_limit(kind: P) -> None:
    limit = STALE_AFTER_DAYS[kind]
    point = price("etf", "2026-01-01", "10", kind=kind)
    assert not is_stale(point, day("2026-01-01"))
    assert not is_stale(point, day("2026-01-01") + timedelta(days=limit))
    assert is_stale(point, day("2026-01-01") + timedelta(days=limit + 1))


def test_thresholds_follow_how_often_each_kind_of_price_changes() -> None:
    assert STALE_AFTER_DAYS[P.MARKET] == 14
    assert STALE_AFTER_DAYS[P.NAV] == 31
    assert STALE_AFTER_DAYS[P.REDEMPTION] == 100
    assert STALE_AFTER_DAYS[P.SUBSCRIPTION] == 100


ETF = instrument("etf", K.ETF)


def valued(prices, on):  # type: ignore[no-untyped-def]
    return value_account(
        account_id="a1",
        entries=[deposit("1000", "2026-01-05"), buy("10", "90", "2026-01-06")],
        instruments={"etf": ETF},
        prices=prices,
        balances=[],
        as_of=day(on),
        currency="EUR",
    )


def test_a_recent_price_is_not_estimated() -> None:
    result = valued([price("etf", "2026-01-20", "92")], "2026-01-31")
    assert not result.estimated and result.warnings == ()


def test_an_old_price_still_values_the_position_but_is_estimated() -> None:
    result = valued([price("etf", "2026-01-10", "92")], "2026-02-10")
    holding = result.positions[0]
    assert holding.value == d("920")
    assert holding.estimated and result.estimated
    assert [w.code for w in result.warnings] == ["price_stale"]
    assert "10/01/2026" in result.warnings[0].message
