"""Empreinte d'une ligne importée et règle de doublon (FR-018, data-model.md).

L'empreinte combine compte, date, type, actif, quantité, prix, montant, frais, libellé et rang
d'occurrence dans le fichier : deux achats identiques du même fichier restent donc distincts, alors
qu'un export plus récent qui reprend les mêmes lignes retrouve les mêmes empreintes. Un identifiant
externe fourni par le fichier l'emporte sur l'empreinte.
"""

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finance.domain.enums import TransactionType


@dataclass(frozen=True)
class LineFacts:
    trade_date: date
    type: TransactionType
    instrument_key: str  # ISIN, sinon nom normalisé ; vide pour un flux de trésorerie
    quantity: Decimal | None
    unit_price: Decimal | None
    amount: Decimal | None
    fees: Decimal
    label: str | None


def _number(value: Decimal | None) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _digest(account_id: str, facts: LineFacts, occurrence: int) -> str:
    parts = [
        account_id,
        facts.trade_date.isoformat(),
        facts.type.value,
        facts.instrument_key,
        _number(facts.quantity),
        _number(facts.unit_price),
        _number(facts.amount),
        _number(facts.fees),
        facts.label or "",
        str(occurrence),
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def fingerprint_lines(account_id: str, lines: Sequence[LineFacts]) -> list[str]:
    """Empreintes des lignes d'un même fichier ; le rang compte les lignes identiques."""
    seen: Counter[LineFacts] = Counter()
    result: list[str] = []
    for facts in lines:
        seen[facts] += 1
        result.append(_digest(account_id, facts, seen[facts]))
    return result


def is_duplicate(
    external_id: str | None,
    fingerprint: str,
    *,
    known_external_ids: set[str],
    known_fingerprints: set[str],
) -> bool:
    if external_id is not None:
        return external_id in known_external_ids
    return fingerprint in known_fingerprints
