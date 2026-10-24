"""Patrimoine net hors dettes : somme exacte des comptes ouverts à une date (FR-021)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finance.domain.entries import Entry
from finance.domain.valuation import (
    AccountValue,
    DeclaredBalanceRow,
    InstrumentInfo,
    PricePoint,
    value_account,
)


@dataclass(frozen=True)
class AccountRef:
    id: str
    opened_on: date
    closed_on: date | None
    currency: str


def is_open_on(ref: AccountRef, on: date) -> bool:
    """Ouvert de sa date d'ouverture jusqu'à la veille de sa clôture."""
    return ref.opened_on <= on and (ref.closed_on is None or on < ref.closed_on)


@dataclass(frozen=True)
class AccountNetWorth:
    account_id: str
    value: Decimal
    estimated: bool


@dataclass(frozen=True)
class AccountWarning:
    account_id: str
    code: str
    instrument_id: str | None
    message: str


@dataclass(frozen=True)
class NetWorth:
    total: Decimal
    currency: str
    estimated: bool
    accounts: tuple[AccountNetWorth, ...]
    warnings: tuple[AccountWarning, ...]
    account_values: tuple[AccountValue, ...]


def compute_net_worth(
    *,
    refs: Sequence[AccountRef],
    entries: Sequence[Entry],
    instruments: Mapping[str, InstrumentInfo],
    prices: Sequence[PricePoint],
    balances: Sequence[DeclaredBalanceRow],
    as_of: date,
    currency: str,
) -> NetWorth:
    """Somme des valeurs des comptes ouverts à `as_of`, dans la devise de référence `currency`.

    Un compte dans une autre devise est laissé de côté et signalé : la conversion arrive avec
    l'histoire US4.
    """
    accounts: list[AccountNetWorth] = []
    values: list[AccountValue] = []
    warnings: list[AccountWarning] = []
    estimated = False
    total = Decimal(0)
    for ref in refs:
        if not is_open_on(ref, as_of):
            continue
        if ref.currency != currency:
            estimated = True
            warnings.append(
                AccountWarning(
                    ref.id,
                    "non_convertible",
                    None,
                    f"Compte en {ref.currency} : conversion en {currency} indisponible.",
                )
            )
            continue
        value = value_account(
            account_id=ref.id,
            entries=entries,
            instruments=instruments,
            prices=prices,
            balances=balances,
            as_of=as_of,
            currency=currency,
        )
        total += value.total
        estimated = estimated or value.estimated
        accounts.append(AccountNetWorth(ref.id, value.total, value.estimated))
        values.append(value)
        warnings.extend(
            AccountWarning(ref.id, w.code, w.instrument_id, w.message) for w in value.warnings
        )
    return NetWorth(
        total=total,
        currency=currency,
        estimated=estimated,
        accounts=tuple(accounts),
        warnings=tuple(warnings),
        account_values=tuple(values),
    )
