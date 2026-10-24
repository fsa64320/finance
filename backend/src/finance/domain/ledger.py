"""Effets de trésorerie et positions, recalculés depuis le journal (jamais stockés)."""

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from finance.domain.entries import Entry, signed_quantity
from finance.domain.enums import TransactionType as T

INFLOWS = frozenset(
    {T.DEPOSIT, T.DIVIDEND, T.DISTRIBUTION, T.INTEREST, T.EMPLOYER_MATCH, T.TRANSFER_IN}
)
OUTFLOWS = frozenset({T.WITHDRAWAL, T.FEE, T.TRANSFER_OUT})
TRADES = frozenset({T.BUY, T.SELL})


def cash_effect(
    kind: T,
    *,
    amount: Decimal | None = None,
    quantity: Decimal | None = None,
    unit_price: Decimal | None = None,
    fees: Decimal = Decimal(0),
) -> Decimal:
    """Effet signé d'une opération sur la trésorerie de son compte (data-model.md)."""
    if fees < 0:
        raise ValueError("Les frais ne peuvent pas être négatifs.")
    if kind in TRADES:
        if amount is not None:
            raise ValueError("Un achat ou une vente n'a pas de montant libre : il est calculé.")
        if quantity is None:
            raise ValueError("La quantité est obligatoire pour un achat ou une vente.")
        if unit_price is None:
            raise ValueError("Le prix unitaire est obligatoire pour un achat ou une vente.")
        if quantity <= 0 or unit_price <= 0:
            raise ValueError("La quantité et le prix unitaire doivent être strictement positifs.")
        gross = quantity * unit_price
        return -(gross + fees) if kind is T.BUY else gross - fees
    if amount is None:
        raise ValueError("Le montant est obligatoire pour cette opération.")
    if amount <= 0:
        raise ValueError("Le montant doit être strictement positif.")
    return amount if kind in INFLOWS else -amount


def _in_scope(entry: Entry, as_of: date, account_id: str | None) -> bool:
    return (
        not entry.voided
        and entry.trade_date <= as_of
        and (account_id is None or entry.account_id == account_id)
    )


def positions(
    entries: Iterable[Entry], *, as_of: date, account_id: str | None = None
) -> dict[tuple[str, str], Decimal]:
    """Quantités détenues par (compte, actif) à `as_of` ; les positions nulles sont omises."""
    held: dict[tuple[str, str], Decimal] = {}
    for entry in entries:
        if entry.instrument_id is None or not _in_scope(entry, as_of, account_id):
            continue
        delta = signed_quantity(entry)
        if delta:
            key = (entry.account_id, entry.instrument_id)
            held[key] = held.get(key, Decimal(0)) + delta
    return {key: quantity for key, quantity in held.items() if quantity != 0}


def cash_balance(entries: Iterable[Entry], *, account_id: str, as_of: date) -> Decimal:
    """Trésorerie d'un compte à `as_of` : somme des effets de ses opérations."""
    total = Decimal(0)
    for entry in entries:
        if _in_scope(entry, as_of, account_id):
            total += entry.cash_amount
    return total
