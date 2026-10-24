"""Principe II et clarification 3 : modifier ou annuler ajoute une version, la dernière fait foi."""

import random
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from finance.domain.entries import (
    Entry,
    active_entries,
    latest_versions,
    new_version,
    restore,
    void,
)
from finance.domain.ledger import cash_balance, positions
from tests.domain_helpers import buy, d, day, deposit, sell


def test_modify_adds_a_version_and_leaves_the_previous_one_untouched() -> None:
    first = buy("10", "90", "2026-01-06")
    second = new_version(first, quantity=d("12"), cash_amount=d("-1080"))
    assert (first.version, second.version) == (1, 2)
    assert first.quantity == d("10") and second.quantity == d("12")
    assert second.transaction_id == first.transaction_id
    assert not second.voided


def test_void_adds_a_voided_version() -> None:
    first = deposit("100", "2026-01-05")
    cancelled = void(first)
    assert cancelled.version == 2 and cancelled.voided
    assert cancelled.cash_amount == first.cash_amount


def test_restore_brings_the_operation_back_with_a_new_version() -> None:
    first = deposit("100", "2026-01-05")
    revived = restore(void(first))
    assert revived.version == 3 and not revived.voided


def test_latest_version_wins_whatever_the_order_of_the_rows() -> None:
    v1 = deposit("100", "2026-01-05")
    v2 = new_version(v1, cash_amount=d("150"))
    v3 = new_version(v2, cash_amount=d("175"))
    for rows in ([v1, v2, v3], [v3, v1, v2], [v2, v3, v1]):
        assert [e.cash_amount for e in latest_versions(rows)] == [d("175")]


def test_voided_latest_version_leaves_the_active_list() -> None:
    v1 = deposit("100", "2026-01-05")
    assert active_entries([v1, void(v1)]) == []


def test_restored_operation_is_active_again() -> None:
    v1 = deposit("100", "2026-01-05")
    v2 = void(v1)
    v3 = restore(v2)
    active = active_entries([v1, v2, v3])
    assert [e.version for e in active] == [3]


def test_active_entries_are_ordered_by_date_then_creation() -> None:
    later = deposit("1", "2026-03-01")
    earlier = deposit("2", "2026-01-01")
    same_day = deposit("3", "2026-01-01")
    ordered = active_entries([later, same_day, earlier])
    assert [e.cash_amount for e in ordered] == [d("2"), d("3"), d("1")]


def test_correcting_a_purchase_corrects_positions_and_cash() -> None:
    original = buy("10", "90", "2026-01-06", fees="1.99")
    corrected = new_version(original, quantity=d("12"), cash_amount=d("-1081.99"))
    rows = [deposit("2000", "2026-01-05"), original, corrected]
    entries = active_entries(rows)
    assert positions(entries, as_of=day("2026-12-31")) == {("a1", "etf"): d("12")}
    assert cash_balance(entries, account_id="a1", as_of=day("2026-12-31")) == d("918.01")


# ---------------------------------------------------------------- propriétés

amounts = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100000"), places=2)
quantities = st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1000"), places=3)
dates = st.dates(min_value=day("2025-01-01"), max_value=day("2026-12-31")).map(
    lambda x: x.isoformat()
)


@st.composite
def histories(draw: st.DrawFn) -> list[Entry]:
    """Opérations avec plusieurs versions chacune, certaines annulées ou rétablies."""
    rows: list[Entry] = []
    for number in range(draw(st.integers(1, 8))):
        base = (
            buy(
                str(draw(quantities)), str(draw(amounts)), draw(dates), transaction_id=f"op{number}"
            )
            if draw(st.booleans())
            else sell(
                str(draw(quantities)), str(draw(amounts)), draw(dates), transaction_id=f"op{number}"
            )
        )
        rows.append(base)
        current = base
        for _ in range(draw(st.integers(0, 3))):
            action = draw(st.sampled_from(["edit", "void", "restore"]))
            if action == "edit":
                current = new_version(current, quantity=draw(quantities))
            elif action == "void":
                current = void(current)
            else:
                current = restore(current)
            rows.append(current)
    return rows


@settings(max_examples=60, deadline=None)
@given(histories(), st.randoms(use_true_random=False))
def test_positions_do_not_depend_on_row_order(rows: list[Entry], rng: random.Random) -> None:
    shuffled = list(rows)
    rng.shuffle(shuffled)
    as_of = day("2026-12-31")
    assert positions(active_entries(rows), as_of=as_of) == positions(
        active_entries(shuffled), as_of=as_of
    )
    assert active_entries(rows) == active_entries(shuffled)


@settings(max_examples=60, deadline=None)
@given(histories())
def test_one_active_entry_per_transaction_with_the_highest_version(rows: list[Entry]) -> None:
    latest = {e.transaction_id: e for e in latest_versions(rows)}
    for entry in rows:
        assert entry.version <= latest[entry.transaction_id].version
    active = active_entries(rows)
    assert len({e.transaction_id for e in active}) == len(active)
    assert all(not e.voided for e in active)
