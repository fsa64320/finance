"""Garde contre les fautes de frappe : les valeurs suivent data-model.md à la lettre."""

from finance.domain.enums import (
    AccountType,
    InstrumentKind,
    PriceKind,
    PriceMode,
    PriceSource,
    RateKind,
    RateSource,
    TransactionType,
)


def values(enum: type) -> list[str]:
    return [member.value for member in enum]  # type: ignore[attr-defined]


def test_account_types() -> None:
    assert values(AccountType) == ["PEE", "PEA", "CTO", "ASSURANCE_VIE", "LIVRET_A"]


def test_instrument_kinds() -> None:
    assert values(InstrumentKind) == [
        "EQUITY",
        "ETF",
        "FUND",
        "FCPE",
        "SCPI",
        "EURO_FUND",
        "CASH",
    ]


def test_transaction_types() -> None:
    assert values(TransactionType) == [
        "DEPOSIT",
        "WITHDRAWAL",
        "BUY",
        "SELL",
        "DIVIDEND",
        "DISTRIBUTION",
        "INTEREST",
        "FEE",
        "EMPLOYER_MATCH",
        "TRANSFER_OUT",
        "TRANSFER_IN",
    ]


def test_price_kinds_modes_and_sources() -> None:
    assert values(PriceKind) == ["MARKET", "NAV", "SUBSCRIPTION", "REDEMPTION"]
    assert values(PriceMode) == ["AUTO", "MANUAL"]
    assert values(PriceSource) == ["PROVIDER", "MANUAL"]


def test_rate_kinds_and_sources() -> None:
    assert values(RateKind) == ["LIVRET_A", "FX"]
    assert values(RateSource) == ["ECB", "MANUAL"]


def test_members_are_plain_strings() -> None:
    assert AccountType.PEA == "PEA"
    assert f"{TransactionType.BUY}" == "BUY"
