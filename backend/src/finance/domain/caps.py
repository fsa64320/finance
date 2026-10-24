"""Plafonds (PEA, Livret A), apports et déblocage du PEE (FR-007 à FR-009)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext

from finance.domain.entries import Entry
from finance.domain.enums import TransactionType as T

DEFAULT_PEA_CAP = Decimal("150000")
DEFAULT_LIVRET_A_CAP = Decimal("22950")


def _scope(entries: Iterable[Entry], account_id: str, as_of: date) -> list[Entry]:
    return [
        entry
        for entry in entries
        if entry.account_id == account_id and not entry.voided and entry.trade_date <= as_of
    ]


def deposits_total(entries: Iterable[Entry], *, account_id: str, as_of: date) -> Decimal:
    """Versements d'un PEA : dépôts et virements entrants ; les retraits ne sont pas déduits."""
    return sum(
        (
            entry.cash_amount
            for entry in _scope(entries, account_id, as_of)
            if entry.type in {T.DEPOSIT, T.TRANSFER_IN}
        ),
        Decimal(0),
    )


@dataclass(frozen=True)
class CapStatus:
    used: Decimal
    cap: Decimal
    remaining: Decimal
    exceeded: bool
    used_percent: Decimal


def cap_status(used: Decimal, cap: Decimal) -> CapStatus:
    """Situation par rapport à un plafond paramétrable."""
    if cap <= 0:
        raise ValueError("Le plafond doit être strictement positif.")
    with localcontext() as context:
        context.prec = 50
        percent = used * 100 / cap
    return CapStatus(
        used=used,
        cap=cap,
        remaining=max(cap - used, Decimal(0)),
        exceeded=used > cap,
        used_percent=percent,
    )


@dataclass(frozen=True)
class Contributions:
    personal: Decimal  # apports nets de l'épargnant : l'abondement n'en fait pas partie
    employer_match: Decimal


def contributions(entries: Iterable[Entry], *, account_id: str, as_of: date) -> Contributions:
    personal = Decimal(0)
    match = Decimal(0)
    for entry in _scope(entries, account_id, as_of):
        if entry.type in {T.DEPOSIT, T.TRANSFER_IN, T.WITHDRAWAL, T.TRANSFER_OUT}:
            personal += entry.cash_amount
        elif entry.type is T.EMPLOYER_MATCH:
            match += entry.cash_amount
    return Contributions(personal=personal, employer_match=match)


@dataclass(frozen=True)
class LockStatus:
    locked: Decimal
    available: Decimal
    next_unlock: date | None


def lock_status(entries: Iterable[Entry], *, account_id: str, as_of: date) -> LockStatus:
    """Versements et abondements du PEE encore bloqués à `as_of`, selon leur date de déblocage."""
    locked = Decimal(0)
    available = Decimal(0)
    upcoming: list[date] = []
    for entry in _scope(entries, account_id, as_of):
        if entry.type not in {T.DEPOSIT, T.EMPLOYER_MATCH}:
            continue
        if entry.unlock_date is not None and entry.unlock_date > as_of:
            locked += entry.cash_amount
            upcoming.append(entry.unlock_date)
        else:
            available += entry.cash_amount
    return LockStatus(locked=locked, available=available, next_unlock=min(upcoming, default=None))
