"""FR-007 et FR-008 : plafond du PEA, apports et déblocage du PEE."""

from decimal import Decimal

import pytest
from finance.domain.caps import (
    DEFAULT_LIVRET_A_CAP,
    DEFAULT_PEA_CAP,
    cap_status,
    contributions,
    deposits_total,
    lock_status,
)

from finance.domain.enums import TransactionType as T
from tests.domain_helpers import d, day, deposit, make, withdrawal


def test_default_caps() -> None:
    assert d("150000") == DEFAULT_PEA_CAP
    assert d("22950") == DEFAULT_LIVRET_A_CAP


def test_pea_deposits_include_incoming_transfers_and_ignore_withdrawals() -> None:
    entries = [
        deposit("100000", "2026-01-05"),
        make(T.TRANSFER_IN, "2026-02-01", cash="20000", group="g1"),
        withdrawal("30000", "2026-03-01"),
        make(T.TRANSFER_OUT, "2026-03-02", cash="-5000", group="g2"),
        deposit("999", "2026-01-05", account="autre"),
    ]
    assert deposits_total(entries, account_id="a1", as_of=day("2026-12-31")) == d("120000")


def test_deposits_respect_the_date() -> None:
    entries = [deposit("100", "2026-01-05"), deposit("50", "2026-06-01")]
    assert deposits_total(entries, account_id="a1", as_of=day("2026-03-01")) == d("100")


def test_cap_status_under_the_cap() -> None:
    status = cap_status(d("120000"), DEFAULT_PEA_CAP)
    assert (status.used, status.cap, status.remaining) == (d("120000"), d("150000"), d("30000"))
    assert not status.exceeded
    assert status.used_percent == d("80")


def test_cap_status_exactly_at_the_cap() -> None:
    status = cap_status(d("150000"), DEFAULT_PEA_CAP)
    assert (status.remaining, status.exceeded, status.used_percent) == (d("0"), False, d("100"))


def test_cap_status_over_the_cap() -> None:
    status = cap_status(d("160000"), DEFAULT_PEA_CAP)
    assert status.exceeded and status.remaining == d("0")
    assert status.used_percent > d("100")


def test_cap_is_configurable() -> None:
    assert cap_status(d("30000"), d("25000")).exceeded


def test_cap_must_be_strictly_positive() -> None:
    with pytest.raises(ValueError, match="plafond"):
        cap_status(d("1"), d("0"))


def test_livret_a_status_uses_the_balance() -> None:
    status = cap_status(d("3500"), DEFAULT_LIVRET_A_CAP)
    assert status.remaining == d("19450")


# ------------------------------------------------------------------- PEE


def pee_entries() -> list:  # type: ignore[type-arg]
    return [
        deposit("1000", "2026-01-05", unlock="2031-01-05"),
        make(T.EMPLOYER_MATCH, "2026-01-05", cash="500", unlock="2031-01-05"),
        deposit("400", "2020-06-01", unlock="2025-06-01"),
        deposit("100", "2026-02-01"),
    ]


def test_employer_match_is_not_a_personal_contribution() -> None:
    result = contributions(pee_entries(), account_id="a1", as_of=day("2026-12-31"))
    assert result.personal == d("1500")
    assert result.employer_match == d("500")


def test_withdrawals_reduce_personal_contributions() -> None:
    entries = [*pee_entries(), withdrawal("200", "2026-05-01")]
    assert contributions(entries, account_id="a1", as_of=day("2026-12-31")).personal == d("1300")


def test_amounts_are_locked_until_their_unlock_date() -> None:
    status = lock_status(pee_entries(), account_id="a1", as_of=day("2026-12-31"))
    assert status.locked == d("1500")
    assert status.available == d("500")
    assert status.next_unlock == day("2031-01-05")


def test_amounts_become_available_on_the_unlock_date() -> None:
    status = lock_status(pee_entries(), account_id="a1", as_of=day("2031-01-05"))
    assert status.locked == d("0")
    assert status.available == d("2000")
    assert status.next_unlock is None


def test_operations_after_as_of_are_ignored_by_the_lock() -> None:
    status = lock_status(pee_entries(), account_id="a1", as_of=day("2020-12-31"))
    assert status.locked == d("400")  # versé en 2020, débloqué en 2025
    assert status.available == d("0")
    assert status.next_unlock == day("2025-06-01")


def test_next_unlock_is_the_earliest_future_date() -> None:
    entries = [
        deposit("100", "2026-01-05", unlock="2033-01-05"),
        deposit("100", "2026-01-06", unlock="2030-01-05"),
    ]
    status = lock_status(entries, account_id="a1", as_of=day("2026-12-31"))
    assert status.next_unlock == day("2030-01-05")
    assert status.locked == d("200")


def test_lock_status_ignores_other_accounts_and_non_contributions() -> None:
    entries = [
        deposit("100", "2026-01-05", unlock="2031-01-05", account="autre"),
        make(T.DIVIDEND, "2026-02-01", cash="10", instrument="f"),
    ]
    status = lock_status(entries, account_id="a1", as_of=day("2026-12-31"))
    assert (status.locked, status.available) == (Decimal(0), Decimal(0))
