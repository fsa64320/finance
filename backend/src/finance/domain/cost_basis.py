"""Prix de revient unitaire moyen pondéré, frais d'achat inclus (research.md §8).

Une vente retire des parts sans changer le prix de revient unitaire des parts restantes. Les frais
de vente touchent la trésorerie, pas le prix de revient. Les divisions se font avec 50 chiffres
significatifs et une seule division par opération pour ne pas cumuler d'arrondis.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext

from finance.domain.entries import Entry
from finance.domain.enums import TransactionType as T

PRECISION = 50


@dataclass(frozen=True)
class CostBasis:
    quantity: Decimal
    total_cost: Decimal
    unit_cost: Decimal | None  # None si aucune part n'est détenue
    oversold: bool  # vrai si les ventes dépassent les achats connus (historique incomplet)


def compute_cost_basis(
    entries: Iterable[Entry], *, account_id: str, instrument_id: str, as_of: date
) -> CostBasis:
    relevant = sorted(
        (
            entry
            for entry in entries
            if entry.account_id == account_id
            and entry.instrument_id == instrument_id
            and entry.type in {T.BUY, T.SELL}
            and not entry.voided
            and entry.trade_date <= as_of
        ),
        key=lambda entry: (entry.trade_date, entry.created_at, entry.transaction_id),
    )
    quantity = Decimal(0)
    total = Decimal(0)
    with localcontext() as context:
        context.prec = PRECISION
        for entry in relevant:
            moved = entry.quantity or Decimal(0)
            if entry.type is T.BUY:
                before = quantity
                quantity += moved
                if quantity <= 0:
                    total = Decimal(0)
                elif before <= 0:
                    # Les parts achetées recouvrent une position négative : le revient repart du
                    # prix de l'achat pour les parts restantes.
                    total = quantity * (entry.unit_price or Decimal(0)) + entry.fees
                else:
                    total += moved * (entry.unit_price or Decimal(0)) + entry.fees
            else:
                before = quantity
                quantity -= moved
                total = Decimal(0) if quantity <= 0 else total * quantity / before
        unit_cost = total / quantity if quantity > 0 else None
    return CostBasis(
        quantity=quantity, total_cost=total, unit_cost=unit_cost, oversold=quantity < 0
    )
