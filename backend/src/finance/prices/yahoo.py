"""Cours et valeurs liquidatives via Yahoo Finance (yfinance), research.md §7.

Source non officielle, susceptible de changer ou de bloquer : toute erreur est absorbée et signalée
sans casser l'application. Seuls un ticker et une période grossière (5d, 1mo, 1y, max) sont envoyés.
"""

from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal

from finance.prices.base import FetchedPrice, PriceBatch, ProviderError

# (ticker, période) -> ([(date, clôture)], devise de cotation)
Download = Callable[[str, str], tuple[list[tuple[date, Decimal]], str | None]]


def _yfinance_history(ticker: str, period: str) -> tuple[list[tuple[date, Decimal]], str | None]:
    import yfinance as yf  # type: ignore[import-untyped]

    handle = yf.Ticker(ticker)
    frame = handle.history(period=period, auto_adjust=False)
    rows = [
        (index.date(), Decimal(repr(round(float(close), 6))))
        for index, close in frame["Close"].dropna().items()
    ]
    currency = None
    try:
        currency = handle.get_history_metadata().get("currency")
    except Exception:
        currency = None
    return rows, currency


class YahooPrices:
    def __init__(self, download: Download | None = None, *, enabled: bool = True) -> None:
        self._download = download or _yfinance_history
        self._enabled = enabled

    def fetch(self, tickers: Sequence[str], *, period: str) -> PriceBatch:
        if not self._enabled:
            raise ProviderError("La source Yahoo Finance est désactivée.")
        found: dict[str, list[FetchedPrice]] = {}
        failed: list[str] = []
        for ticker in tickers:
            try:
                rows, currency = self._download(ticker, period)
            except Exception:
                failed.append(ticker)
                continue
            if not rows:
                failed.append(ticker)
                continue
            code = currency or "EUR"
            scale = Decimal(1)
            if code == "GBp":  # la Bourse de Londres cote en pence
                code, scale = "GBP", Decimal(100)
            found[ticker] = [
                FetchedPrice(ticker, on, value / scale if scale != 1 else value, code)
                for on, value in rows
            ]
        return PriceBatch(found=found, failed=failed)
