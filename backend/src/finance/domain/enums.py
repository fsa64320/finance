"""Énumérations du domaine. Les valeurs suivent data-model.md à la lettre."""

from enum import StrEnum


class AccountType(StrEnum):
    PEE = "PEE"
    PEA = "PEA"
    CTO = "CTO"
    ASSURANCE_VIE = "ASSURANCE_VIE"
    LIVRET_A = "LIVRET_A"


class InstrumentKind(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    FUND = "FUND"
    FCPE = "FCPE"
    SCPI = "SCPI"
    EURO_FUND = "EURO_FUND"
    CASH = "CASH"


class PriceMode(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class TransactionType(StrEnum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    DISTRIBUTION = "DISTRIBUTION"
    INTEREST = "INTEREST"
    FEE = "FEE"
    EMPLOYER_MATCH = "EMPLOYER_MATCH"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


class PriceKind(StrEnum):
    MARKET = "MARKET"
    NAV = "NAV"
    SUBSCRIPTION = "SUBSCRIPTION"
    REDEMPTION = "REDEMPTION"


class PriceSource(StrEnum):
    PROVIDER = "PROVIDER"
    MANUAL = "MANUAL"


class RateKind(StrEnum):
    LIVRET_A = "LIVRET_A"
    FX = "FX"


class RateSource(StrEnum):
    ECB = "ECB"
    MANUAL = "MANUAL"
