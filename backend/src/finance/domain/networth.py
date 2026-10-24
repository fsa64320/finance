"""Patrimoine net hors dettes : somme exacte des comptes ouverts à une date (FR-021)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finance.domain.entries import Entry
from finance.domain.fx import FxTable
from finance.domain.livret_a import LivretASchedule, RateRow
from finance.domain.valuation import (
    AccountValue,
    DeclaredBalanceRow,
    InstrumentInfo,
    PositionValue,
    PricePoint,
    convert_amount,
    value_account,
)


@dataclass(frozen=True)
class AccountRef:
    id: str
    opened_on: date
    closed_on: date | None
    currency: str
    is_livret_a: bool = False  # ses intérêts sont estimés d'après la table de taux


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


def convert_account_value(
    value: AccountValue, total: Decimal, currency: str, as_of: date, fx: FxTable | None
) -> AccountValue:
    """Valeur du compte exprimée dans la devise de référence, composante par composante."""

    def to_reference(amount: Decimal) -> Decimal:
        converted = convert_amount(amount, value.currency, currency, as_of, fx).value
        return amount if converted is None else converted

    return AccountValue(
        account_id=value.account_id,
        as_of=value.as_of,
        currency=currency,
        cash=to_reference(value.cash),
        positions=tuple(
            PositionValue(
                instrument_id=p.instrument_id,
                kind=p.kind,
                quantity=p.quantity,
                total_cost=to_reference(p.total_cost),
                unit_cost=None if p.unit_cost is None else to_reference(p.unit_cost),
                price=p.price,
                price_date=p.price_date,
                value=None if p.value is None else to_reference(p.value),
                estimated=p.estimated,
                subscription_price=p.subscription_price,
            )
            for p in value.positions
        ),
        total=total,
        estimated=value.estimated,
        warnings=value.warnings,
        interest_estimate=to_reference(value.interest_estimate),
    )


def compute_net_worth(
    *,
    refs: Sequence[AccountRef],
    entries: Sequence[Entry],
    instruments: Mapping[str, InstrumentInfo],
    prices: Sequence[PricePoint],
    balances: Sequence[DeclaredBalanceRow],
    as_of: date,
    currency: str,
    fx: FxTable | None = None,
    livret_rates: Sequence[RateRow] = (),
) -> NetWorth:
    """Somme des valeurs des comptes ouverts à `as_of`, dans la devise de référence `currency`.

    Un compte dans une autre devise est converti au taux de `as_of` ; sans taux, il est laissé de
    côté et signalé plutôt que compté faux.
    """
    accounts: list[AccountNetWorth] = []
    values: list[AccountValue] = []
    warnings: list[AccountWarning] = []
    estimated = False
    total = Decimal(0)
    for ref in refs:
        if not is_open_on(ref, as_of):
            continue
        schedule = (
            LivretASchedule.from_entries(entries, ref.id, livret_rates, until=as_of)
            if ref.is_livret_a
            else None
        )
        value = value_account(
            account_id=ref.id,
            entries=entries,
            instruments=instruments,
            prices=prices,
            balances=balances,
            as_of=as_of,
            currency=ref.currency,
            fx=fx,
            livret=schedule,
        )
        account_total = value.total
        account_estimated = value.estimated
        if ref.currency != currency:
            converted = convert_amount(value.total, ref.currency, currency, as_of, fx)
            if converted.value is None:
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
            account_total = converted.value
            if converted.code == "rate_stale":
                account_estimated = True
                warnings.append(
                    AccountWarning(
                        ref.id,
                        "rate_stale",
                        None,
                        f"Taux de change {ref.currency}/{currency} ancien : la valeur est estimée.",
                    )
                )
            value = convert_account_value(value, account_total, currency, as_of, fx)
        total += account_total
        estimated = estimated or account_estimated
        accounts.append(AccountNetWorth(ref.id, account_total, account_estimated))
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
