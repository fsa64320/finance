"""Sources de prix simulées pour les tests d'API : aucune ne sort sur le réseau."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from finance.prices.base import (
    FetchedPrice,
    FetchedRate,
    PriceBatch,
    ProviderError,
    Providers,
    TickerSuggestion,
)


class FakeRates:
    def __init__(self, rates: list[FetchedRate] | None = None, error: str | None = None) -> None:
        self.rates = rates if rates is not None else []
        self.error = error
        self.calls = 0

    def fetch(self) -> list[FetchedRate]:
        self.calls += 1
        if self.error:
            raise ProviderError(self.error)
        return list(self.rates)


class FakePrices:
    def __init__(
        self,
        prices: dict[str, list[tuple[date, str]]] | None = None,
        failed: list[str] | None = None,
        error: str | None = None,
        currency: str = "EUR",
    ) -> None:
        self.prices = prices or {}
        self.failed = failed or []
        self.error = error
        self.currency = currency
        self.calls: list[tuple[list[str], str]] = []

    def fetch(self, tickers: list[str], *, period: str) -> PriceBatch:
        self.calls.append((list(tickers), period))
        if self.error:
            raise ProviderError(self.error)
        found = {
            ticker: [
                FetchedPrice(ticker, on, Decimal(value), self.currency)
                for on, value in self.prices[ticker]
            ]
            for ticker in tickers
            if ticker in self.prices
        }
        failed = [t for t in tickers if t in self.failed or t not in self.prices]
        return PriceBatch(found=found, failed=failed)


class FakeTickers:
    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def suggest(self, isin: str) -> list[TickerSuggestion]:
        self.calls.append(isin)
        if self.error:
            raise ProviderError(self.error)
        return [TickerSuggestion("CW8.PA", "FP", "AMUNDI MSCI WORLD")]


def install(client: TestClient, **overrides: object) -> Providers:
    """Remplace les sources de l'application ; renvoie l'ensemble installé."""
    providers = Providers(
        rates=overrides.get("rates") or FakeRates(),  # type: ignore[arg-type]
        prices=overrides.get("prices") or FakePrices(),  # type: ignore[arg-type]
        tickers=overrides.get("tickers") or FakeTickers(),  # type: ignore[arg-type]
    )
    client.app.state.providers = providers  # type: ignore[attr-defined]
    return providers


def recent(days_ago: int = 1) -> date:
    return date.today() - timedelta(days=days_ago)
