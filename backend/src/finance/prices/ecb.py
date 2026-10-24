"""Taux de change de la Banque centrale européenne (research.md §7).

Taux de référence quotidiens, publiés en général vers 16 h CET les jours ouvrés, contre l'euro. Le
fichier des 90 derniers jours suffit à compléter l'historique à chaque mise à jour. La BCE précise
que ces taux sont publiés à titre d'information : assez pour valoriser un patrimoine, pas pour
une transaction.
"""

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from finance.prices.base import FetchedRate, ProviderError

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
_NS = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"
_TIMEOUT = 10.0


class EcbRates:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=_TIMEOUT, follow_redirects=False)

    def fetch(self) -> list[FetchedRate]:
        try:
            response = self._client.get(ECB_URL)
        except httpx.HTTPError as error:
            raise ProviderError(f"BCE injoignable : {error}") from error
        if response.status_code != 200:
            raise ProviderError(f"BCE indisponible (réponse {response.status_code}).")
        content = response.content
        if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
            raise ProviderError("BCE : document refusé (déclaration de type ou d'entité).")
        try:
            root = ET.fromstring(content)  # noqa: S314  (aucune entité possible, vérifié ci-dessus)
        except ET.ParseError as error:
            raise ProviderError("BCE : réponse illisible.") from error

        rates: list[FetchedRate] = []
        for day in root.iter(f"{_NS}Cube"):
            stamp = day.get("time")
            if stamp is None:
                continue
            try:
                rate_date = date.fromisoformat(stamp)
            except ValueError:
                continue
            for cube in day.findall(f"{_NS}Cube"):
                currency, raw = cube.get("currency"), cube.get("rate")
                if not currency or raw is None:
                    continue
                try:
                    value = Decimal(raw)
                except InvalidOperation:
                    continue
                if value.is_finite() and value > 0:
                    rates.append(FetchedRate(currency, rate_date, value))
        return rates
