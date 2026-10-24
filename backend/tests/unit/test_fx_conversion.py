"""FR-025 : conversion au taux de la date de valorisation, « non convertible » sans taux."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from finance.domain.enums import InstrumentKind as K
from finance.domain.fx import FX_STALE_AFTER_DAYS, FxRateRow, FxTable
from finance.domain.networth import AccountRef, compute_net_worth
from finance.domain.valuation import value_account
from tests.domain_helpers import buy, d, day, deposit, instrument, price

BASE = datetime(2026, 1, 1, 9, tzinfo=UTC)


def rate(quote: str, on: str, value: str, recorded: int = 0, base: str = "EUR") -> FxRateRow:
    return FxRateRow(
        base=base,
        quote=quote,
        effective_from=day(on),
        value=d(value),
        recorded_at=BASE + timedelta(minutes=recorded),
    )


TABLE = FxTable(
    [
        rate("USD", "2026-01-02", "1.10"),
        rate("USD", "2026-01-10", "1.20"),
        rate("GBP", "2026-01-02", "0.85"),
    ]
)


def close(a: Decimal, b: str) -> bool:
    return abs(a - d(b)) < d("1e-20")


class TestConversion:
    def test_foreign_to_base_divides_by_the_rate(self) -> None:
        result = TABLE.convert(d("110"), "USD", "EUR", day("2026-01-05"))
        assert result is not None
        assert result.amount == d("100") and result.rate_date == day("2026-01-02")
        assert close(result.rate, "0.90909090909090909090909")

    def test_base_to_foreign_multiplies(self) -> None:
        result = TABLE.convert(d("100"), "EUR", "USD", day("2026-01-05"))
        assert result is not None and result.amount == d("110")

    def test_the_rate_of_the_valuation_date_applies(self) -> None:
        result = TABLE.convert(d("120"), "USD", "EUR", day("2026-01-10"))
        assert result is not None and result.amount == d("100")

    def test_days_without_publication_reuse_the_last_known_rate(self) -> None:
        result = TABLE.convert(d("110"), "USD", "EUR", day("2026-01-09"))
        assert result is not None and result.amount == d("100")
        assert result.rate_date == day("2026-01-02")

    def test_no_rate_yet_means_not_convertible(self) -> None:
        assert TABLE.convert(d("110"), "USD", "EUR", day("2026-01-01")) is None

    def test_an_unknown_currency_is_not_convertible(self) -> None:
        assert TABLE.convert(d("1"), "JPY", "EUR", day("2026-01-31")) is None

    def test_same_currency_needs_no_rate(self) -> None:
        result = FxTable([]).convert(d("42.5"), "EUR", "EUR", day("2026-01-31"))
        assert result is not None and (result.amount, result.rate) == (d("42.5"), d("1"))

    def test_two_foreign_currencies_go_through_the_euro(self) -> None:
        result = TABLE.convert(d("110"), "USD", "GBP", day("2026-01-05"))
        assert result is not None and close(result.amount, "85")  # 110 USD = 100 EUR = 85 GBP

    def test_a_rate_published_against_another_base_is_inverted(self) -> None:
        table = FxTable([rate("EUR", "2026-01-02", "0.8", base="USD")])
        result = table.convert(d("100"), "EUR", "USD", day("2026-01-05"))
        assert result is not None and close(result.amount, "125")

    def test_on_the_same_effective_date_the_latest_entry_wins(self) -> None:
        table = FxTable(
            [
                rate("USD", "2026-01-02", "1.10", recorded=1),
                rate("USD", "2026-01-02", "1.25", recorded=7),
            ]
        )
        result = table.convert(d("125"), "USD", "EUR", day("2026-01-05"))
        assert result is not None and result.amount == d("100")

    def test_the_amounts_stay_exact_decimals(self) -> None:
        result = TABLE.convert(d("0.01"), "USD", "EUR", day("2026-01-05"))
        assert result is not None and isinstance(result.amount, Decimal)


ETF_USD = instrument("etf", K.ETF, currency="USD")


def valued(fx, prices, on="2026-01-31"):  # type: ignore[no-untyped-def]
    return value_account(
        account_id="a1",
        entries=[deposit("2000", "2026-01-03"), buy("10", "90", "2026-01-04")],
        instruments={"etf": ETF_USD},
        prices=prices,
        balances=[],
        as_of=day(on),
        currency="EUR",
        fx=fx,
    )


class TestValuation:
    def test_a_price_in_another_currency_is_converted_at_the_valuation_date(self) -> None:
        result = valued(TABLE, [price("etf", "2026-01-14", "120", currency="USD")], on="2026-01-14")
        holding = result.positions[0]
        assert holding.value == d("1000")  # 10 x 120 USD / 1,20
        assert result.total == d("1100") + d("1000")  # 2000 - 900 en trésorerie

    def test_a_fresh_rate_leaves_the_value_unestimated(self) -> None:
        result = valued(TABLE, [price("etf", "2026-01-14", "120", currency="USD")], on="2026-01-14")
        assert not result.estimated and result.warnings == ()

    def test_a_rate_older_than_the_limit_flags_the_value_as_estimated(self) -> None:
        on = day("2026-01-10") + timedelta(days=FX_STALE_AFTER_DAYS + 1)
        table = FxTable([rate("USD", "2026-01-10", "1.20")])
        result = valued(
            table, [price("etf", on.isoformat(), "120", currency="USD")], on=on.isoformat()
        )
        assert result.positions[0].value == d("1000") and result.positions[0].estimated
        assert [w.code for w in result.warnings] == ["rate_stale"]

    def test_the_limit_itself_is_not_stale(self) -> None:
        on = day("2026-01-10") + timedelta(days=FX_STALE_AFTER_DAYS)
        table = FxTable([rate("USD", "2026-01-10", "1.20")])
        result = valued(
            table, [price("etf", on.isoformat(), "120", currency="USD")], on=on.isoformat()
        )
        assert not result.estimated

    def test_without_a_rate_the_position_is_not_convertible_and_left_out(self) -> None:
        result = valued(FxTable([]), [price("etf", "2026-01-20", "120", currency="USD")])
        holding = result.positions[0]
        assert holding.value is None and holding.estimated
        assert [w.code for w in result.warnings] == ["non_convertible"]
        assert result.total == result.cash

    def test_without_any_table_it_behaves_as_before(self) -> None:
        result = valued(None, [price("etf", "2026-01-20", "120", currency="USD")])
        assert result.positions[0].value is None
        assert [w.code for w in result.warnings] == ["non_convertible"]


class TestAccountsInAnotherCurrency:
    def refs(self):  # type: ignore[no-untyped-def]
        return [AccountRef("usd", day("2026-01-01"), None, "USD")]

    def net(self, fx, on="2026-01-08"):  # type: ignore[no-untyped-def]
        return compute_net_worth(
            refs=self.refs(),
            entries=[deposit("1100", "2026-01-03", account="usd", currency="USD")],
            instruments={},
            prices=[],
            balances=[],
            as_of=day(on),
            currency="EUR",
            fx=fx,
        )

    def test_the_account_is_converted_into_the_reference_currency(self) -> None:
        result = self.net(TABLE)
        assert result.total == d("1000") and not result.estimated and result.warnings == ()

    def test_a_stale_rate_flags_the_total(self) -> None:
        result = self.net(TABLE, on="2026-01-09")  # 7 jours après le 2
        assert not result.estimated
        later = FxTable([rate("USD", "2026-01-02", "1.10")])
        far = compute_net_worth(
            refs=self.refs(),
            entries=[deposit("1100", "2026-01-03", account="usd", currency="USD")],
            instruments={},
            prices=[],
            balances=[],
            as_of=day("2026-02-15"),
            currency="EUR",
            fx=later,
        )
        assert far.total == d("1000") and far.estimated
        assert [w.code for w in far.warnings] == ["rate_stale"]

    def test_without_a_rate_the_account_is_left_out_and_reported(self) -> None:
        result = self.net(FxTable([]))
        assert result.total == d("0") and result.estimated
        assert [w.code for w in result.warnings] == ["non_convertible"]
