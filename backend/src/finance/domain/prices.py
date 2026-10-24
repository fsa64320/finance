"""Prix applicable à une date et prix « ancien » (FR-013, FR-025, research.md §8)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from finance.domain.enums import PriceKind

# Au-delà de ce délai, un prix reste utilisé mais la valeur est signalée « estimée ». Les seuils
# suivent la fréquence à laquelle chaque sorte de prix change : un cours quotidien (un mois de
# retard est déjà une source en panne), une valeur liquidative hebdomadaire ou mensuelle (publiée
# avec un délai), un prix de SCPI révisé au trimestre.
STALE_AFTER_DAYS: Mapping[PriceKind, int] = {
    PriceKind.MARKET: 30,
    PriceKind.NAV: 45,
    PriceKind.SUBSCRIPTION: 100,
    PriceKind.REDEMPTION: 100,
}


@dataclass(frozen=True)
class PricePoint:
    instrument_id: str
    price_date: date
    kind: PriceKind
    value: Decimal
    currency: str
    recorded_at: datetime


def select_price(
    prices: Iterable[PricePoint], instrument_id: str, kind: PriceKind, as_of: date
) -> PricePoint | None:
    """Dernier prix de cette sorte à `as_of` ou avant ; à date égale, la saisie la plus récente
    (puis, à égalité parfaite, la première reçue)."""
    candidates = [
        price
        for price in prices
        if price.instrument_id == instrument_id and price.kind is kind and price.price_date <= as_of
    ]
    return max(candidates, key=lambda p: (p.price_date, p.recorded_at), default=None)


def is_stale(price: PricePoint, as_of: date) -> bool:
    return (as_of - price.price_date).days > STALE_AFTER_DAYS[price.kind]
