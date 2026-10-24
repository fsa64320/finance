"""data-model.md, règles de validation des opérations (erreurs bloquantes et avertissements)."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from finance.domain.rules import RuleResult, check_transaction

from finance.domain.enums import AccountType as A
from finance.domain.enums import TransactionType as T


def check(**overrides: Any) -> RuleResult:
    values: dict[str, Any] = {
        "account_type": A.CTO,
        "account_opened_on": date(2026, 1, 2),
        "type": T.DEPOSIT,
        "trade_date": date(2026, 1, 5),
        "amount": Decimal("100"),
    }
    values.update(overrides)
    return check_transaction(**values)


def buy(**overrides: Any) -> RuleResult:
    values: dict[str, Any] = {
        "type": T.BUY,
        "amount": None,
        "has_instrument": True,
        "quantity": Decimal("10"),
        "unit_price": Decimal("90"),
        "fees": Decimal("1.99"),
    }
    values.update(overrides)
    return check(**values)


def codes(result: RuleResult) -> set[str]:
    return {violation.code for violation in result.errors}


def test_a_plain_deposit_is_valid() -> None:
    result = check()
    assert result.ok and not result.errors and not result.warnings


def test_a_plain_purchase_is_valid() -> None:
    assert buy().ok


@pytest.mark.parametrize("account_type", [A.PEA, A.CTO, A.ASSURANCE_VIE, A.LIVRET_A])
def test_employer_match_is_only_allowed_on_a_pee(account_type: A) -> None:
    assert "employer_match_pee_only" in codes(
        check(type=T.EMPLOYER_MATCH, account_type=account_type)
    )


def test_employer_match_is_fine_on_a_pee() -> None:
    assert check(type=T.EMPLOYER_MATCH, account_type=A.PEE).ok


@pytest.mark.parametrize("kind", [T.BUY, T.SELL])
def test_buying_or_selling_on_a_livret_a_is_refused(kind: T) -> None:
    assert "livret_a_cash_only" in codes(buy(type=kind, account_type=A.LIVRET_A))


def test_trade_date_cannot_precede_the_opening() -> None:
    assert "before_opening" in codes(check(trade_date=date(2026, 1, 1)))
    assert check(trade_date=date(2026, 1, 2)).ok


@pytest.mark.parametrize("kind", [T.BUY, T.SELL])
@pytest.mark.parametrize("quantity", [None, Decimal(0), Decimal("-1")])
def test_quantity_must_be_strictly_positive_for_trades(kind: T, quantity: Decimal | None) -> None:
    assert "quantity_positive" in codes(buy(type=kind, quantity=quantity))


@pytest.mark.parametrize("kind", [T.BUY, T.SELL])
@pytest.mark.parametrize("price", [None, Decimal(0), Decimal("-1")])
def test_unit_price_must_be_strictly_positive_for_trades(kind: T, price: Decimal | None) -> None:
    assert "unit_price_positive" in codes(buy(type=kind, unit_price=price))


def test_fees_cannot_be_negative() -> None:
    assert "fees_not_negative" in codes(buy(fees=Decimal("-0.01")))
    assert buy(fees=Decimal(0)).ok


@pytest.mark.parametrize("kind", [T.BUY, T.SELL, T.DIVIDEND, T.DISTRIBUTION])
def test_instrument_is_required_for_these_types(kind: T) -> None:
    arguments: dict[str, Any] = {"type": kind, "has_instrument": False}
    if kind in {T.BUY, T.SELL}:
        arguments |= {"quantity": Decimal(1), "unit_price": Decimal(1), "amount": None}
    assert "instrument_required" in codes(check(**arguments))


@pytest.mark.parametrize("kind", [T.DEPOSIT, T.WITHDRAWAL, T.FEE, T.TRANSFER_OUT, T.TRANSFER_IN])
def test_pure_cash_flows_refuse_an_instrument(kind: T) -> None:
    assert "instrument_forbidden" in codes(
        check(type=kind, has_instrument=True, transfer_group_id="g")
    )


def test_interest_accepts_an_optional_instrument() -> None:
    assert check(type=T.INTEREST, has_instrument=True).ok
    assert check(type=T.INTEREST, has_instrument=False).ok


@pytest.mark.parametrize("kind", [T.DEPOSIT, T.DIVIDEND, T.INTEREST, T.FEE])
def test_quantity_and_price_are_empty_outside_trades(kind: T) -> None:
    arguments: dict[str, Any] = {"type": kind, "quantity": Decimal(1), "unit_price": Decimal(1)}
    if kind == T.DIVIDEND:
        arguments["has_instrument"] = True
    assert "trade_fields_forbidden" in codes(check(**arguments))


@pytest.mark.parametrize("kind", [T.TRANSFER_OUT, T.TRANSFER_IN])
def test_transfers_need_a_group(kind: T) -> None:
    assert "transfer_group_required" in codes(check(type=kind))
    assert check(type=kind, transfer_group_id="g1").ok


def test_other_types_refuse_a_transfer_group() -> None:
    assert "transfer_group_forbidden" in codes(check(transfer_group_id="g1"))


def test_unlock_date_is_for_pee_contributions_only() -> None:
    unlock = date(2031, 1, 5)
    assert check(account_type=A.PEE, unlock_date=unlock).ok
    assert check(account_type=A.PEE, type=T.EMPLOYER_MATCH, unlock_date=unlock).ok
    assert "unlock_date_pee_only" in codes(check(account_type=A.CTO, unlock_date=unlock))
    assert "unlock_date_contribution_only" in codes(
        check(account_type=A.PEE, type=T.WITHDRAWAL, unlock_date=unlock)
    )


@pytest.mark.parametrize("amount", [None, Decimal(0), Decimal("-3")])
def test_cash_flows_need_a_positive_amount(amount: Decimal | None) -> None:
    assert "amount_positive" in codes(check(amount=amount))


def test_selling_more_than_held_is_a_warning_not_an_error() -> None:
    result = buy(type=T.SELL, quantity=Decimal(12), fees=Decimal(0), held_quantity=Decimal(10))
    assert result.ok
    assert [warning.code for warning in result.warnings] == ["oversell"]


def test_selling_what_is_held_raises_no_warning() -> None:
    result = buy(type=T.SELL, quantity=Decimal(10), fees=Decimal(0), held_quantity=Decimal(10))
    assert result.ok and not result.warnings


def test_without_holdings_information_no_oversell_warning() -> None:
    assert not buy(type=T.SELL, fees=Decimal(0)).warnings


def test_all_errors_are_reported_together_with_french_messages() -> None:
    result = buy(account_type=A.LIVRET_A, quantity=Decimal(0), trade_date=date(2025, 1, 1))
    assert {"livret_a_cash_only", "quantity_positive", "before_opening"} <= codes(result)
    assert all(violation.message and violation.field for violation in result.errors)
