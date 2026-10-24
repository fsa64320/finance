"""Interfaces des sources externes de prix, de taux et de tickers (FR-029).

Seuls des identifiants d'actifs (ticker, ISIN) et des devises sortent d'une source : jamais de
quantité, de montant, de nom de compte ni de date d'opération. Une source qui échoue lève
`ProviderError` ; l'application continue avec les derniers prix connus (FR-013).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol


class ProviderError(Exception):
    """La source est injoignable, a refusé la demande ou a répondu de façon illisible."""


@dataclass(frozen=True)
class FetchedPrice:
    ticker: str
    price_date: date
    value: Decimal
    currency: str


@dataclass(frozen=True)
class FetchedRate:
    quote: str  # devise cotée ; la base est l'euro (1 EUR = value quote)
    rate_date: date
    value: Decimal


@dataclass(frozen=True)
class TickerSuggestion:
    ticker: str
    exchange: str
    name: str


@dataclass(frozen=True)
class PriceBatch:
    found: dict[str, list[FetchedPrice]] = field(default_factory=dict)
    failed: list[str] = field(default_factory=list)


class PriceProvider(Protocol):
    def fetch(self, tickers: Sequence[str], *, period: str) -> PriceBatch: ...


class RateProvider(Protocol):
    def fetch(self) -> list[FetchedRate]: ...


class TickerSearch(Protocol):
    def suggest(self, isin: str) -> list[TickerSuggestion]: ...


@dataclass
class Providers:
    rates: RateProvider
    prices: PriceProvider
    tickers: TickerSearch
