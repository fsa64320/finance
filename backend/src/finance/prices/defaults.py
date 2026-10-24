"""Sources réelles de l'application ; les tests les remplacent par des doubles."""

from finance.prices.base import Providers
from finance.prices.ecb import EcbRates
from finance.prices.openfigi import OpenFigi
from finance.prices.yahoo import YahooPrices


def default_providers() -> Providers:
    return Providers(rates=EcbRates(), prices=YahooPrices(), tickers=OpenFigi())
