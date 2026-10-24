"""FR-022 : évolution du patrimoine, recalculée depuis le journal et les prix à chaque date."""

import random
from datetime import timedelta
from decimal import Decimal
from itertools import pairwise

from finance.domain.networth import AccountRef, compute_net_worth
from finance.domain.series import (
    DAILY_LIMIT_DAYS,
    SeriesPoint,
    net_worth_series,
    period_start,
    sample_dates,
)
from hypothesis import given, settings
from hypothesis import strategies as st

from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind
from finance.domain.enums import TransactionType as T
from tests.domain_helpers import buy, d, day, declared, deposit, instrument, make, price, sell

ETF = instrument("etf", K.ETF)
FUND = instrument("fe", K.EURO_FUND)
INSTRUMENTS = {"etf": ETF, "fe": FUND}


def ref(identifier: str = "a", opened: str = "2025-01-01", closed: str | None = None) -> AccountRef:
    return AccountRef(
        id=identifier,
        opened_on=day(opened),
        closed_on=None if closed is None else day(closed),
        currency="EUR",
    )


def series(refs, entries, dates, prices=(), balances=()):  # type: ignore[no-untyped-def]
    return net_worth_series(
        refs=refs,
        entries=entries,
        instruments=INSTRUMENTS,
        prices=list(prices),
        balances=list(balances),
        dates=dates,
        currency="EUR",
    )


def values(points: list[SeriesPoint]) -> dict[str, Decimal]:
    return {p.date.isoformat(): p.value for p in points}


# --------------------------------------------------------------- échantillonnage


def test_range_up_to_a_year_is_daily() -> None:
    dates = sample_dates(day("2026-01-01"), day("2026-12-31"))
    assert len(dates) == 365
    assert dates[0] == day("2026-01-01") and dates[-1] == day("2026-12-31")
    assert all(b - a == timedelta(days=1) for a, b in pairwise(dates))


def test_daily_limit_is_a_year_plus_a_leap_day() -> None:
    assert DAILY_LIMIT_DAYS == 366
    start = day("2025-01-01")
    assert len(sample_dates(start, start + timedelta(days=366))) == 367
    assert sample_dates(start, start + timedelta(days=367))[1] - start == timedelta(days=7)


def test_longer_ranges_are_weekly_and_always_end_on_the_last_day() -> None:
    dates = sample_dates(day("2016-01-01"), day("2026-01-01"))
    assert dates[0] == day("2016-01-01") and dates[-1] == day("2026-01-01")
    gaps = {(b - a).days for a, b in pairwise(dates)}
    assert gaps <= {7, 1, 2, 3, 4, 5, 6}
    assert len({(b - a).days for a, b in pairwise(dates[:-1])}) == 1
    assert 520 <= len(dates) <= 530
    assert dates == sorted(set(dates))


def test_single_day_range_has_one_point() -> None:
    assert sample_dates(day("2026-01-01"), day("2026-01-01")) == [day("2026-01-01")]


def test_start_after_end_is_refused() -> None:
    import pytest

    with pytest.raises(ValueError, match="début"):
        sample_dates(day("2026-02-01"), day("2026-01-01"))


def test_period_starts() -> None:
    end = day("2026-03-31")
    assert period_start("1m", end, earliest=None) == day("2026-02-28")
    assert period_start("3m", end, earliest=None) == day("2025-12-31")
    assert period_start("1y", end, earliest=None) == day("2025-03-31")
    assert period_start("5y", end, earliest=None) == day("2021-03-31")
    assert period_start("all", end, earliest=day("2020-06-15")) == day("2020-06-15")
    assert period_start("all", end, earliest=None) == end


def test_unknown_period_is_refused() -> None:
    import pytest

    with pytest.raises(ValueError, match="période"):
        period_start("7y", day("2026-01-01"), earliest=None)


# -------------------------------------------------------------------- valeurs


def scenario():  # type: ignore[no-untyped-def]
    return [
        deposit("1000", "2026-01-05"),
        buy("10", "90", "2026-01-06", fees="1.99"),
    ]


def test_value_follows_the_journal_and_the_latest_known_price() -> None:
    prices = [price("etf", "2026-01-10", "90.2"), price("etf", "2026-01-20", "95")]
    dates = [
        day(x)
        for x in (
            "2026-01-04",
            "2026-01-05",
            "2026-01-06",
            "2026-01-10",
            "2026-01-15",
            "2026-01-20",
        )
    ]
    points = series([ref()], scenario(), dates, prices)
    assert values(points) == {
        "2026-01-04": d("0"),
        "2026-01-05": d("1000"),
        "2026-01-06": d("1000"),  # sans prix : valorisé au prix de revient (901,99 + 98,01)
        "2026-01-10": d("1000.01"),
        "2026-01-15": d("1000.01"),  # dernier prix connu
        "2026-01-20": d("1048.01"),
    }


def test_points_are_estimated_while_a_price_is_missing() -> None:
    prices = [price("etf", "2026-01-10", "90.2")]
    points = series(
        [ref()], scenario(), [day("2026-01-05"), day("2026-01-06"), day("2026-01-10")], prices
    )
    assert [(p.date.isoformat(), p.estimated) for p in points] == [
        ("2026-01-05", False),
        ("2026-01-06", True),
        ("2026-01-10", False),
    ]


def test_closed_account_disappears_from_its_closing_date() -> None:
    entries = [deposit("500", "2026-01-05", account="a"), deposit("300", "2026-01-05", account="b")]
    refs = [ref("a"), ref("b", closed="2026-02-01")]
    points = series(refs, entries, [day("2026-01-31"), day("2026-02-01"), day("2026-03-01")])
    assert [p.value for p in points] == [d("800"), d("500"), d("500")]


def test_account_joins_from_its_opening_date() -> None:
    entries = [deposit("500", "2026-03-05", account="late")]
    points = series(
        [ref("late", opened="2026-03-01")], entries, [day("2026-02-28"), day("2026-03-05")]
    )
    assert [p.value for p in points] == [d("0"), d("500")]


def test_euro_fund_uses_the_latest_declaration_and_flows_after_it() -> None:
    entries = [
        make(T.BUY, "2026-01-10", cash="-1000", instrument="fe", quantity="1000", unit_price="1"),
        make(T.SELL, "2026-02-10", cash="200", instrument="fe", quantity="200", unit_price="1"),
    ]
    balances = [
        declared("fe", "2026-01-01", "5000"),
        declared("fe", "2026-03-01", "6000", recorded=5),
    ]
    points = series(
        [ref()],
        [deposit("10000", "2026-01-02"), *entries],
        [day("2026-01-05"), day("2026-01-15"), day("2026-02-15"), day("2026-03-05")],
        balances=balances,
    )
    # trésorerie : 10000 puis -1000 puis +200 ; fonds : 5000, +1000, -200, puis 6000 déclaré
    assert values(points) == {
        "2026-01-05": d("10000") + d("5000"),
        "2026-01-15": d("9000") + d("6000"),
        "2026-02-15": d("9200") + d("5800"),
        "2026-03-05": d("9200") + d("6000"),
    }


def test_euro_fund_without_declaration_counts_for_zero_and_is_estimated() -> None:
    entries = [
        deposit("2000", "2026-01-02"),
        make(T.BUY, "2026-01-10", cash="-1000", instrument="fe", quantity="1000", unit_price="1"),
    ]
    points = series([ref()], entries, [day("2026-01-15")])
    assert (points[0].value, points[0].estimated) == (d("1000"), True)


def test_no_data_gives_no_point_when_there_is_no_account() -> None:
    assert series([], [], [day("2026-01-01")]) == []


def test_dates_must_be_ascending() -> None:
    import pytest

    with pytest.raises(ValueError, match="croissant"):
        series([ref()], [], [day("2026-01-02"), day("2026-01-01")])


# ------------------------------------------- équivalence avec le calcul date par date


@st.composite
def histories(draw: st.DrawFn):  # type: ignore[no-untyped-def]
    entries = [
        deposit("5000", "2025-01-02", account="a"),
        deposit("3000", "2025-01-02", account="b"),
    ]
    for _ in range(draw(st.integers(0, 12))):
        account = draw(st.sampled_from(["a", "b"]))
        when = (day("2025-01-03") + timedelta(days=draw(st.integers(0, 400)))).isoformat()
        quantity = str(draw(st.integers(1, 20)))
        cost = str(draw(st.integers(1, 200)))
        kind = draw(st.sampled_from(["buy", "sell", "fund_in", "fund_out", "cash"]))
        if kind == "buy":
            entries.append(buy(quantity, cost, when, fees="0.5", account=account))
        elif kind == "sell":
            entries.append(sell(quantity, cost, when, account=account))
        elif kind == "fund_in":
            entries.append(
                make(
                    T.BUY,
                    when,
                    cash=f"-{quantity}",
                    instrument="fe",
                    quantity=quantity,
                    unit_price="1",
                    account=account,
                )
            )
        elif kind == "fund_out":
            entries.append(
                make(
                    T.SELL,
                    when,
                    cash=quantity,
                    instrument="fe",
                    quantity=quantity,
                    unit_price="1",
                    account=account,
                )
            )
        else:
            entries.append(deposit(quantity, when, account=account))
    prices = [
        price(
            "etf",
            (day("2025-01-01") + timedelta(days=draw(st.integers(0, 400)))).isoformat(),
            str(draw(st.integers(1, 300))),
            recorded=draw(st.integers(0, 5)),
        )
        for _ in range(draw(st.integers(0, 6)))
    ]
    balances = [
        declared(
            "fe",
            (day("2025-01-01") + timedelta(days=draw(st.integers(0, 400)))).isoformat(),
            str(draw(st.integers(0, 9000))),
            recorded=draw(st.integers(0, 5)),
            account=draw(st.sampled_from(["a", "b"])),
        )
        for _ in range(draw(st.integers(0, 3)))
    ]
    return entries, prices, balances


@settings(max_examples=40, deadline=None)
@given(histories(), st.randoms(use_true_random=False))
def test_the_sweep_matches_a_full_recomputation_on_every_date(history, rng: random.Random) -> None:  # type: ignore[no-untyped-def]
    entries, prices, balances = history
    rng.shuffle(entries)
    refs = [ref("a"), ref("b", closed="2025-12-01")]
    dates = sample_dates(day("2025-01-01"), day("2026-03-01"))[::9]
    points = series(refs, entries, dates, prices, balances)
    for point in points:
        expected = compute_net_worth(
            refs=refs,
            entries=entries,
            instruments=INSTRUMENTS,
            prices=prices,
            balances=balances,
            as_of=point.date,
            currency="EUR",
        )
        assert point.value == expected.total, point.date
        assert point.estimated == expected.estimated, point.date


def test_price_kind_reference_is_the_market_price_for_etf() -> None:
    assert price("etf", "2026-01-01", "1").kind is PriceKind.MARKET
