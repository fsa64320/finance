"""FR-006 : un fonds en euros n'a pas de cours ; sa valeur vient du dernier solde déclaré."""

from finance.domain.enums import InstrumentKind
from finance.domain.enums import TransactionType as T
from finance.domain.valuation import AccountValue, PositionValue, value_account
from tests.domain_helpers import d, day, declared, deposit, instrument, make

FUND = instrument("fe", InstrumentKind.EURO_FUND)


def value(entries, balances, on="2026-01-31") -> AccountValue:  # type: ignore[no-untyped-def]
    return value_account(
        account_id="a1",
        entries=entries,
        instruments={"fe": FUND},
        prices=[],
        balances=balances,
        as_of=day(on),
        currency="EUR",
    )


def fund_value(result: AccountValue) -> PositionValue:
    return next(p for p in result.positions if p.instrument_id == "fe")


def invest(amount: str, on: str):  # type: ignore[no-untyped-def]
    return make(T.BUY, on, cash=f"-{amount}", instrument="fe", quantity=amount, unit_price="1")


def withdraw(amount: str, on: str):  # type: ignore[no-untyped-def]
    return make(T.SELL, on, cash=amount, instrument="fe", quantity=amount, unit_price="1")


def test_value_is_the_declared_balance() -> None:
    result = value([], [declared("fe", "2026-01-01", "5000")])
    assert fund_value(result).value == d("5000")
    assert result.total == d("5000")


def test_flows_after_the_declaration_are_added() -> None:
    entries = [invest("1000", "2026-01-10"), withdraw("200", "2026-01-20")]
    result = value(entries, [declared("fe", "2026-01-01", "5000")])
    assert fund_value(result).value == d("5800")


def test_flows_on_or_before_the_declaration_are_already_included() -> None:
    entries = [invest("1000", "2026-01-01"), invest("300", "2025-12-20")]
    result = value(entries, [declared("fe", "2026-01-01", "5000")])
    assert fund_value(result).value == d("5000")


def test_flows_after_the_valuation_date_are_ignored() -> None:
    entries = [invest("1000", "2026-02-10")]
    assert fund_value(value(entries, [declared("fe", "2026-01-01", "5000")])).value == d("5000")


def test_the_latest_declaration_before_the_date_wins() -> None:
    balances = [declared("fe", "2026-01-01", "4000"), declared("fe", "2026-07-01", "5000")]
    entries = [invest("100", "2026-03-01"), invest("10", "2026-07-15")]
    assert fund_value(value(entries, balances, on="2026-06-01")).value == d("4100")
    assert fund_value(value(entries, balances, on="2026-08-01")).value == d("5010")


def test_a_declaration_after_the_valuation_date_is_ignored() -> None:
    result = value([], [declared("fe", "2026-03-01", "5000")], on="2026-01-31")
    assert fund_value(result).value == d("0")


def test_two_declarations_on_the_same_date_use_the_most_recent_entry() -> None:
    balances = [
        declared("fe", "2026-01-01", "4000", recorded=10),
        declared("fe", "2026-01-01", "5000", recorded=30),
        declared("fe", "2026-01-01", "4500", recorded=20),
    ]
    assert fund_value(value([], balances)).value == d("5000")


def test_without_a_declaration_the_value_is_zero_with_a_message() -> None:
    result = value([invest("1000", "2026-01-10")], [])
    position = fund_value(result)
    assert position.value == d("0")
    assert position.estimated
    assert [w.code for w in result.warnings] == ["declared_balance_missing"]
    assert result.warnings[0].instrument_id == "fe"
    assert "solde" in result.warnings[0].message
    assert result.estimated


def test_investing_in_the_fund_reduces_the_cash_of_the_account() -> None:
    entries = [deposit("6000", "2026-01-02"), invest("1000", "2026-01-10")]
    result = value(entries, [declared("fe", "2026-01-10", "1000")])
    assert result.cash == d("5000")
    assert result.total == d("6000")


def test_declaration_of_another_account_is_ignored() -> None:
    entries = [invest("100", "2026-01-10")]
    result = value(entries, [declared("fe", "2026-01-01", "5000", account="autre")])
    assert fund_value(result).value == d("0")
    assert [w.code for w in result.warnings] == ["declared_balance_missing"]


def test_a_declared_balance_makes_the_fund_appear_without_any_purchase() -> None:
    result = value([], [declared("fe", "2026-01-01", "5000")])
    assert [p.instrument_id for p in result.positions] == ["fe"]
    assert not result.estimated


def test_a_balance_in_another_currency_cannot_be_converted_yet() -> None:
    result = value([], [declared("fe", "2026-01-01", "5000", currency="USD")])
    assert fund_value(result).value is None
    assert [w.code for w in result.warnings] == ["non_convertible"]
    assert result.total == d("0")
