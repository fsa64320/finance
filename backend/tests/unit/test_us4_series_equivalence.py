"""La série se calcule par balayage ; elle doit rester identique au recalcul complet, y compris avec
conversions de devises, prix anciens, SCPI et Livret A (FR-022, US4)."""

from datetime import UTC, date, datetime, timedelta

from finance.domain.fx import FxRateRow, FxTable
from finance.domain.livret_a import RateRow

from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind as P
from finance.domain.networth import AccountRef, compute_net_worth
from finance.domain.series import net_worth_series
from tests.domain_helpers import (
    buy,
    d,
    day,
    declared,
    deposit,
    instrument,
    price,
    sell,
    withdrawal,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def fx_row(quote: str, on: str, value: str) -> FxRateRow:
    return FxRateRow("EUR", quote, day(on), d(value), NOW)


def test_the_sweep_matches_a_full_recomputation_with_every_us4_feature() -> None:
    refs = [
        AccountRef("pea", day("2025-01-01"), None, "EUR"),
        AccountRef("usd", day("2025-02-01"), day("2026-10-01"), "USD"),
        AccountRef("liv", day("2025-01-01"), None, "EUR", is_livret_a=True),
    ]
    entries = [
        deposit("20000", "2025-01-05", account="pea"),
        buy("10", "90", "2025-01-10", fees="2", account="pea"),
        buy("50", "100", "2025-03-03", instrument="us", account="pea"),
        buy("4", "250", "2025-04-01", fees="10", instrument="scpi", account="pea"),
        sell("5", "95", "2025-09-09", account="pea"),
        deposit("5000", "2025-02-10", account="usd", currency="USD"),
        deposit("1000", "2025-01-20", account="liv"),
        deposit("300", "2025-07-16", account="liv"),
        withdrawal("200", "2025-11-15", account="liv"),
    ]
    instruments = {
        "etf": instrument("etf", K.ETF),
        "us": instrument("us", K.ETF, currency="USD"),
        "scpi": instrument("scpi", K.SCPI),
        "fe": instrument("fe", K.EURO_FUND),
    }
    prices = [
        price("etf", "2025-01-12", "91"),
        price("etf", "2025-06-01", "99"),  # puis plus rien : devient ancien
        price("us", "2025-03-05", "110", currency="USD"),
        price("us", "2025-12-01", "130", currency="USD"),
        price("scpi", "2025-04-01", "250", kind=P.SUBSCRIPTION),
        price("scpi", "2025-04-02", "228", kind=P.REDEMPTION),
        price("scpi", "2026-01-02", "231", kind=P.REDEMPTION),
    ]
    balances = [declared("fe", "2025-05-01", "3000", account="usd", currency="USD")]
    fx = FxTable(
        [
            fx_row("USD", "2025-01-02", "1.04"),
            fx_row("USD", "2025-06-02", "1.15"),
            fx_row("USD", "2026-03-02", "1.08"),
        ]
    )
    rates = [
        RateRow(day("2025-01-01"), d("3"), NOW),
        RateRow(day("2025-08-01"), d("2.4"), NOW),
        RateRow(day("2026-02-01"), d("1.7"), NOW),
    ]
    start, end = day("2025-01-01"), day("2026-12-31")
    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=9)
    dates.append(end)

    points = net_worth_series(
        refs=refs,
        entries=entries,
        instruments=instruments,
        prices=prices,
        balances=balances,
        dates=dates,
        currency="EUR",
        fx=fx,
        livret_rates=rates,
    )
    assert len(points) == len(dates)
    for point in points:
        full = compute_net_worth(
            refs=refs,
            entries=entries,
            instruments=instruments,
            prices=prices,
            balances=balances,
            as_of=point.date,
            currency="EUR",
            fx=fx,
            livret_rates=rates,
        )
        assert (point.value, point.estimated) == (full.total, full.estimated), point.date
    assert any(p.estimated for p in points) and any(not p.estimated for p in points)
