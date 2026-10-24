"""Répartition du patrimoine par classe d'actifs (FR-023).

Les poids sont des pourcentages à deux décimales dont la somme vaut exactement 100 : l'arrondi se
fait par la méthode du plus fort reste, pas par arrondi indépendant de chaque poids.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal, localcontext
from enum import StrEnum

from finance.domain.enums import InstrumentKind
from finance.domain.valuation import AccountValue


class AssetClass(StrEnum):
    """Classes d'actifs affichées ; l'ordre est celui de l'affichage."""

    EQUITIES_ETF = "equities_etf"
    FUNDS = "funds"
    SCPI = "scpi"
    EURO_FUNDS = "euro_funds"
    CASH = "cash"


_CLASS_OF_KIND = {
    InstrumentKind.EQUITY: AssetClass.EQUITIES_ETF,
    InstrumentKind.ETF: AssetClass.EQUITIES_ETF,
    InstrumentKind.FUND: AssetClass.FUNDS,
    InstrumentKind.FCPE: AssetClass.FUNDS,
    InstrumentKind.SCPI: AssetClass.SCPI,
    InstrumentKind.EURO_FUND: AssetClass.EURO_FUNDS,
    InstrumentKind.CASH: AssetClass.CASH,
}

_CENT = Decimal("0.01")


def asset_class_of(kind: InstrumentKind) -> AssetClass:
    return _CLASS_OF_KIND[kind]


@dataclass(frozen=True)
class Slice:
    asset_class: AssetClass
    value: Decimal
    weight_percent: Decimal


def split_weights(amounts: Sequence[Decimal]) -> list[Decimal]:
    """Pourcentages à deux décimales des `amounts`, de somme exactement 100 (plus fort reste)."""
    total = sum(amounts, Decimal(0))
    if not amounts or total <= 0:
        raise ValueError("Le total à répartir doit être strictement positif.")
    with localcontext() as context:
        context.prec = 50
        exact = [amount * 100 / total for amount in amounts]
        floors = [value.quantize(_CENT, rounding=ROUND_FLOOR) for value in exact]
        remainders = [value - floor for value, floor in zip(exact, floors, strict=True)]
        missing_cents = int((Decimal(100) - sum(floors, Decimal(0))) / _CENT)
        order = sorted(range(len(amounts)), key=lambda index: (-remainders[index], index))
        weights = list(floors)
        for index in order[:missing_cents]:
            weights[index] += _CENT
    return weights


def compute_allocation(account_values: Iterable[AccountValue]) -> list[Slice]:
    """Valeur et poids de chaque classe d'actifs, sur les classes de valeur strictement positive."""
    totals = dict.fromkeys(AssetClass, Decimal(0))
    for account in account_values:
        totals[AssetClass.CASH] += account.cash
        for position in account.positions:
            if position.value is not None:
                totals[asset_class_of(position.kind)] += position.value
    classes = [(kind, value) for kind, value in totals.items() if value > 0]
    if not classes:
        return []
    weights = split_weights([value for _, value in classes])
    return [
        Slice(asset_class=kind, value=value, weight_percent=weight)
        for (kind, value), weight in zip(classes, weights, strict=True)
    ]
