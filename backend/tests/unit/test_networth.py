"""FR-021 : patrimoine net hors dettes, somme exacte des comptes ouverts à la date."""

from decimal import Decimal

from finance.domain.networth import AccountRef, compute_net_worth, is_open_on

from finance.domain.enums import InstrumentKind as K
from tests.domain_helpers import buy, d, day, deposit, instrument, price

ETF = instrument("etf", K.ETF)


def ref(
    identifier: str, opened: str = "2026-01-02", closed: str | None = None, currency: str = "EUR"
) -> AccountRef:
    return AccountRef(
        id=identifier,
        opened_on=day(opened),
        closed_on=None if closed is None else day(closed),
        currency=currency,
    )


def worth(refs, entries, on="2026-12-31", prices=(), balances=(), currency="EUR"):  # type: ignore[no-untyped-def]
    return compute_net_worth(
        refs=refs,
        entries=entries,
        instruments={"etf": ETF},
        prices=list(prices),
        balances=list(balances),
        as_of=day(on),
        currency=currency,
    )


def pea_and_livret():  # type: ignore[no-untyped-def]
    return [
        deposit("1000", "2026-01-05", account="pea"),
        buy("10", "90", "2026-01-06", fees="1.99", account="pea"),
        deposit("3000", "2026-01-03", account="livret"),
    ]


def test_sum_of_open_accounts_is_exact() -> None:
    result = worth(
        [ref("pea"), ref("livret")],
        pea_and_livret(),
        prices=[price("etf", "2026-01-10", "90.2")],
    )
    assert result.total == d("4000.01")
    assert {a.account_id: a.value for a in result.accounts} == {
        "pea": d("1000.01"),
        "livret": d("3000"),
    }
    assert not result.estimated and result.warnings == ()


def test_decimal_sum_does_not_drift() -> None:
    entries = [deposit("0.1", "2026-01-05", account="a"), deposit("0.2", "2026-01-05", account="b")]
    assert worth([ref("a"), ref("b")], entries).total == d("0.3")


def test_empty_patrimony_is_zero() -> None:
    result = worth([], [])
    assert (result.total, result.estimated, result.accounts, result.warnings) == (
        d("0"),
        False,
        (),
        (),
    )


def test_closed_account_leaves_the_current_total_but_stays_in_the_past() -> None:
    refs = [ref("pea"), ref("livret", closed="2026-06-30")]
    entries = pea_and_livret()
    assert worth(
        refs, entries, on="2026-12-31", prices=[price("etf", "2026-01-10", "90.2")]
    ).total == d("1000.01")
    assert worth(
        refs, entries, on="2026-03-01", prices=[price("etf", "2026-01-10", "90.2")]
    ).total == d("4000.01")


def test_account_is_open_from_its_opening_date_until_the_day_before_closing() -> None:
    account = ref("x", opened="2026-01-02", closed="2026-06-30")
    assert not is_open_on(account, day("2026-01-01"))
    assert is_open_on(account, day("2026-01-02"))
    assert is_open_on(account, day("2026-06-29"))
    assert not is_open_on(account, day("2026-06-30"))
    assert is_open_on(ref("y"), day("2099-01-01"))


def test_not_yet_opened_account_is_left_out() -> None:
    refs = [ref("pea"), ref("late", opened="2026-09-01")]
    entries = [*pea_and_livret(), deposit("500", "2026-09-05", account="late")]
    assert [a.account_id for a in worth(refs, entries, on="2026-06-30").accounts] == ["pea"]
    assert {a.account_id for a in worth(refs, entries, on="2026-12-31").accounts} == {"pea", "late"}


def test_estimated_flag_and_warnings_name_their_account() -> None:
    result = worth([ref("pea")], pea_and_livret()[:2])
    assert result.estimated
    assert [(w.account_id, w.code, w.instrument_id) for w in result.warnings] == [
        ("pea", "price_missing", "etf")
    ]
    assert result.accounts[0].estimated


def test_account_in_another_currency_is_left_out_and_flagged() -> None:
    refs = [ref("pea"), ref("usd", currency="USD")]
    entries = [
        deposit("1000", "2026-01-05", account="pea"),
        deposit("500", "2026-01-05", account="usd", currency="USD"),
    ]
    result = worth(refs, entries)
    assert result.total == d("1000")
    assert result.estimated
    assert [(w.account_id, w.code) for w in result.warnings] == [("usd", "non_convertible")]
    assert "usd" not in {a.account_id for a in result.accounts}


def test_negative_cash_reduces_the_total() -> None:
    entries = [
        deposit("100", "2026-01-05", account="a"),
        buy("10", "90", "2026-01-06", account="a"),
    ]
    result = worth([ref("a")], entries, prices=[price("etf", "2026-01-10", "90")])
    assert result.total == d("100") - d("900") + d("900")
    assert isinstance(result.total, Decimal)
