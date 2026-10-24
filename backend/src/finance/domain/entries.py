"""Opérations du journal vues par le domaine : lignes de version immuables.

Une opération a une identité stable (`transaction_id`) et une ligne par version. La dernière
version fait foi ; modifier, annuler ou rétablir ajoute une version (principe II).
"""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from finance.domain.enums import TransactionType


@dataclass(frozen=True)
class Entry:
    transaction_id: str
    version: int
    account_id: str
    type: TransactionType
    trade_date: date
    cash_amount: Decimal  # effet signé sur la trésorerie du compte
    currency: str
    created_at: datetime
    voided: bool = False
    instrument_id: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    fees: Decimal = Decimal(0)
    unlock_date: date | None = None
    transfer_group_id: str | None = None
    label: str | None = None


def _order(entry: Entry) -> tuple[date, datetime, str]:
    return (entry.trade_date, entry.created_at, entry.transaction_id)


def latest_versions(rows: Iterable[Entry]) -> list[Entry]:
    """Dernière version de chaque opération (annulées comprises), triées par date puis création."""
    latest: dict[str, Entry] = {}
    for row in rows:
        known = latest.get(row.transaction_id)
        if known is None or row.version > known.version:
            latest[row.transaction_id] = row
    return sorted(latest.values(), key=_order)


def active_entries(rows: Iterable[Entry]) -> list[Entry]:
    """Opérations en vigueur : dernière version, hors annulations."""
    return [entry for entry in latest_versions(rows) if not entry.voided]


def new_version(entry: Entry, **changes: Any) -> Entry:
    """Nouvelle version de `entry` avec `changes` ; l'original n'est pas modifié."""
    return replace(entry, version=entry.version + 1, **changes)


def void(entry: Entry) -> Entry:
    return new_version(entry, voided=True)


def restore(entry: Entry) -> Entry:
    return new_version(entry, voided=False)


def signed_quantity(entry: Entry) -> Decimal:
    """Variation de quantité détenue : positive pour un achat, négative pour une vente."""
    quantity = entry.quantity or Decimal(0)
    if entry.type is TransactionType.BUY:
        return quantity
    if entry.type is TransactionType.SELL:
        return -quantity
    return Decimal(0)
