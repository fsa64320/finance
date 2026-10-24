"""Clarification 2 : un virement entre comptes est neutre et se gère par groupe de deux jambes."""

from decimal import Decimal

import pytest

from finance.domain.entries import Entry
from finance.domain.enums import TransactionType as T
from finance.domain.ledger import cash_balance
from finance.domain.transfers import (
    TransferLegs,
    make_transfer,
    update_transfer,
    validate_transfer,
    void_transfer,
)
from tests.domain_helpers import d, day, deposit


def transfer(amount: str = "500", on: str = "2026-03-01") -> TransferLegs:
    return make_transfer(
        group_id="g1",
        out_transaction_id="t-out",
        in_transaction_id="t-in",
        from_account="pea",
        to_account="livret",
        amount=d(amount),
        trade_date=day(on),
        currency="EUR",
        created_at=deposit("1", "2026-01-01").created_at,
    )


def balances(entries: list[Entry]) -> tuple[Decimal, Decimal]:
    as_of = day("2026-12-31")
    return (
        cash_balance(entries, account_id="pea", as_of=as_of),
        cash_balance(entries, account_id="livret", as_of=as_of),
    )


def opening() -> list[Entry]:
    return [
        deposit("2000", "2026-01-05", account="pea"),
        deposit("3000", "2026-01-05", account="livret"),
    ]


def test_legs_have_opposite_types_and_the_same_amount_date_and_group() -> None:
    legs = transfer()
    assert (legs.out.type, legs.into.type) == (T.TRANSFER_OUT, T.TRANSFER_IN)
    assert legs.out.cash_amount == d("-500")
    assert legs.into.cash_amount == d("500")
    assert legs.out.trade_date == legs.into.trade_date == day("2026-03-01")
    assert legs.out.transfer_group_id == legs.into.transfer_group_id == "g1"
    assert (legs.out.account_id, legs.into.account_id) == ("pea", "livret")
    assert legs.out.transaction_id != legs.into.transaction_id


def test_transfer_moves_money_and_leaves_the_total_unchanged() -> None:
    entries = opening()
    before = balances(entries)
    legs = transfer()
    after = balances([*entries, legs.out, legs.into])
    assert before == (d("2000"), d("3000"))
    assert after == (d("1500"), d("3500"))
    assert sum(after) == sum(before)


@pytest.mark.parametrize("amount", ["0.01", "123.45", "1999.99"])
def test_neutrality_holds_for_any_amount(amount: str) -> None:
    entries = opening()
    legs = transfer(amount)
    assert sum(balances([*entries, legs.out, legs.into])) == d("5000")


def test_same_account_is_refused() -> None:
    with pytest.raises(ValueError, match="deux comptes différents"):
        make_transfer(
            group_id="g",
            out_transaction_id="a",
            in_transaction_id="b",
            from_account="pea",
            to_account="pea",
            amount=d("10"),
            trade_date=day("2026-03-01"),
            currency="EUR",
            created_at=deposit("1", "2026-01-01").created_at,
        )


@pytest.mark.parametrize("amount", ["0", "-5"])
def test_amount_must_be_strictly_positive(amount: str) -> None:
    with pytest.raises(ValueError, match="positif"):
        transfer(amount)


def test_validate_accepts_well_formed_legs() -> None:
    legs = transfer()
    validate_transfer(legs.out, legs.into)


def test_validate_refuses_legs_that_do_not_match() -> None:
    legs = transfer()
    from dataclasses import replace

    cases = {
        "montant": replace(legs.into, cash_amount=d("499")),
        "date": replace(legs.into, trade_date=day("2026-03-02")),
        "devise": replace(legs.into, currency="USD"),
        "groupe": replace(legs.into, transfer_group_id="autre"),
        "comptes": replace(legs.into, account_id="pea"),
        "types": replace(legs.into, type=T.TRANSFER_OUT),
    }
    for reason, broken in cases.items():
        with pytest.raises(ValueError, match=reason):
            validate_transfer(legs.out, broken)


def test_update_changes_both_legs_together_and_bumps_both_versions() -> None:
    legs = transfer()
    updated = update_transfer(legs, amount=d("750"), trade_date=day("2026-03-10"))
    assert (updated.out.cash_amount, updated.into.cash_amount) == (d("-750"), d("750"))
    assert updated.out.trade_date == updated.into.trade_date == day("2026-03-10")
    assert (updated.out.version, updated.into.version) == (2, 2)
    validate_transfer(updated.out, updated.into)
    assert legs.out.cash_amount == d("-500")  # l'original n'est pas modifié


def test_void_cancels_both_legs_together() -> None:
    legs = void_transfer(transfer())
    assert legs.out.voided and legs.into.voided
    assert (legs.out.version, legs.into.version) == (2, 2)
    from finance.domain.entries import active_entries

    assert active_entries([legs.out, legs.into]) == []


def test_update_refuses_a_non_positive_amount() -> None:
    with pytest.raises(ValueError, match="positif"):
        update_transfer(transfer(), amount=d("0"))
