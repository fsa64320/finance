"""Aide à la saisie du ticker via OpenFIGI v3 (research.md §7).

Déclenchée par l'utilisateur, sans clé : 25 requêtes par minute. Seul le code ISIN est envoyé.
"""

import re
import time
from collections import deque
from collections.abc import Callable

import httpx

from finance.prices.base import ProviderError, TickerSuggestion

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
REQUESTS_PER_MINUTE = 25
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")
_TIMEOUT = 10.0

# Code de place OpenFIGI -> suffixe de ticker attendu par Yahoo Finance.
_YAHOO_SUFFIX = {
    "FP": ".PA",
    "GY": ".DE",
    "GR": ".DE",
    "LN": ".L",
    "NA": ".AS",
    "IM": ".MI",
    "SM": ".MC",
    "BB": ".BR",
    "SW": ".SW",
    "PL": ".LS",
    "ID": ".IR",
    "AV": ".VI",
    "FH": ".HE",
    "SS": ".ST",
    "DC": ".CO",
    "NO": ".OL",
}


class OpenFigi:
    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client or httpx.Client(timeout=_TIMEOUT, follow_redirects=False)
        self._clock = clock
        self._sent: deque[float] = deque()

    def _reserve(self) -> None:
        now = self._clock()
        while self._sent and now - self._sent[0] >= 60:
            self._sent.popleft()
        if len(self._sent) >= REQUESTS_PER_MINUTE:
            raise ProviderError(
                "OpenFIGI : limite de 25 demandes par minute atteinte, réessayez dans une minute."
            )
        self._sent.append(now)

    def suggest(self, isin: str) -> list[TickerSuggestion]:
        if not _ISIN.fullmatch(isin):
            raise ProviderError("Code ISIN invalide : rien n'a été envoyé à OpenFIGI.")
        self._reserve()
        try:
            response = self._client.post(
                OPENFIGI_URL, json=[{"idType": "ID_ISIN", "idValue": isin}]
            )
        except httpx.HTTPError as error:
            raise ProviderError(f"OpenFIGI injoignable : {error}") from error
        if response.status_code == 429:
            raise ProviderError("OpenFIGI : trop de demandes, réessayez dans une minute.")
        if response.status_code != 200:
            raise ProviderError(f"OpenFIGI indisponible (réponse {response.status_code}).")
        try:
            body = response.json()
            items = body[0].get("data", []) if body else []
        except (ValueError, AttributeError, IndexError, KeyError, TypeError) as error:
            raise ProviderError("OpenFIGI : réponse illisible.") from error

        suggestions: list[TickerSuggestion] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            ticker, exchange = item.get("ticker"), item.get("exchCode")
            if not ticker or not exchange or item.get("marketSector") != "Equity":
                continue
            if (ticker, exchange) in seen:
                continue
            seen.add((ticker, exchange))
            suggestions.append(
                TickerSuggestion(
                    ticker=f"{ticker}{_YAHOO_SUFFIX.get(exchange, '')}",
                    exchange=exchange,
                    name=item.get("name") or ticker,
                )
            )
        return suggestions
