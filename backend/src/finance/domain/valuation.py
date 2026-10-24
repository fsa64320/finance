"""Valeur d'un compte à une date : trésorerie + positions (research.md §8).

Tout est recalculé depuis le journal, les prix et les soldes déclarés. Quand un prix manque, la
position est valorisée à son prix de revient et signalée « estimée » (FR-025). Les prix en devise
étrangère et les règles propres aux SCPI et au Livret A arrivent avec l'histoire US4.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from finance.domain.cost_basis import compute_cost_basis
from finance.domain.entries import Entry
from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind
from finance.domain.enums import TransactionType as T
from finance.domain.ledger import cash_balance

PRICE_KIND_BY_INSTRUMENT: Mapping[K, PriceKind] = {
    K.EQUITY: PriceKind.MARKET,
    K.ETF: PriceKind.MARKET,
    K.FUND: PriceKind.NAV,
    K.FCPE: PriceKind.NAV,
    K.SCPI: PriceKind.REDEMPTION,
}


@dataclass(frozen=True)
class InstrumentInfo:
    id: str
    kind: K
    currency: str


@dataclass(frozen=True)
class PricePoint:
    instrument_id: str
    price_date: date
    kind: PriceKind
    value: Decimal
    currency: str
    recorded_at: datetime


@dataclass(frozen=True)
class DeclaredBalanceRow:
    account_id: str
    instrument_id: str
    balance_date: date
    amount: Decimal
    currency: str
    recorded_at: datetime


@dataclass(frozen=True)
class ValuationWarning:
    code: str
    instrument_id: str | None
    message: str


@dataclass(frozen=True)
class PositionValue:
    instrument_id: str
    kind: K
    quantity: Decimal
    total_cost: Decimal
    unit_cost: Decimal | None
    price: Decimal | None
    price_date: date | None
    value: Decimal | None  # None si la position n'a pas pu être valorisée
    estimated: bool


@dataclass(frozen=True)
class AccountValue:
    account_id: str
    as_of: date
    currency: str
    cash: Decimal
    positions: tuple[PositionValue, ...]
    total: Decimal
    estimated: bool
    warnings: tuple[ValuationWarning, ...]


def _latest_price(
    prices: Iterable[PricePoint], instrument_id: str, kind: PriceKind, as_of: date
) -> PricePoint | None:
    candidates = [
        price
        for price in prices
        if price.instrument_id == instrument_id and price.kind is kind and price.price_date <= as_of
    ]
    return max(candidates, key=lambda p: (p.price_date, p.recorded_at), default=None)


def _value_priced(
    info: K,
    instrument_id: str,
    entries: Sequence[Entry],
    prices: Sequence[PricePoint],
    account_id: str,
    as_of: date,
    currency: str,
    warnings: list[ValuationWarning],
) -> PositionValue | None:
    basis = compute_cost_basis(
        entries, account_id=account_id, instrument_id=instrument_id, as_of=as_of
    )
    if basis.quantity == 0:
        return None
    price = _latest_price(prices, instrument_id, PRICE_KIND_BY_INSTRUMENT[info], as_of)

    def result(value: Decimal | None, estimated: bool) -> PositionValue:
        return PositionValue(
            instrument_id=instrument_id,
            kind=info,
            quantity=basis.quantity,
            total_cost=basis.total_cost,
            unit_cost=basis.unit_cost,
            price=None if price is None else price.value,
            price_date=None if price is None else price.price_date,
            value=value,
            estimated=estimated,
        )

    if basis.quantity < 0:
        warnings.append(
            ValuationWarning(
                "negative_position",
                instrument_id,
                "Plus de parts vendues que d'achetées : l'historique est incomplet.",
            )
        )
        return result(None, True)
    if price is None:
        warnings.append(
            ValuationWarning(
                "price_missing",
                instrument_id,
                "Aucun prix connu : valorisé au prix de revient.",
            )
        )
        return result(basis.total_cost, True)
    if price.currency != currency:
        warnings.append(
            ValuationWarning(
                "non_convertible",
                instrument_id,
                f"Prix en {price.currency} : conversion en {currency} indisponible.",
            )
        )
        return result(None, True)
    return result(basis.quantity * price.value, False)


def _value_euro_fund(
    instrument_id: str,
    entries: Sequence[Entry],
    balances: Sequence[DeclaredBalanceRow],
    account_id: str,
    as_of: date,
    currency: str,
    warnings: list[ValuationWarning],
) -> PositionValue:
    basis = compute_cost_basis(
        entries, account_id=account_id, instrument_id=instrument_id, as_of=as_of
    )
    eligible = [
        balance
        for balance in balances
        if balance.account_id == account_id
        and balance.instrument_id == instrument_id
        and balance.balance_date <= as_of
    ]
    latest = max(eligible, key=lambda b: (b.balance_date, b.recorded_at), default=None)
    value: Decimal | None
    estimated = False
    if latest is None:
        value, estimated = Decimal(0), True
        warnings.append(
            ValuationWarning(
                "declared_balance_missing",
                instrument_id,
                "Aucun solde déclaré : déclarez le solde du fonds en euros pour le valoriser.",
            )
        )
    elif latest.currency != currency:
        value, estimated = None, True
        warnings.append(
            ValuationWarning(
                "non_convertible",
                instrument_id,
                f"Solde en {latest.currency} : conversion en {currency} indisponible.",
            )
        )
    else:
        flows = Decimal(0)
        for entry in entries:
            if (
                entry.account_id == account_id
                and entry.instrument_id == instrument_id
                and entry.type in {T.BUY, T.SELL}
                and not entry.voided
                and latest.balance_date < entry.trade_date <= as_of
            ):
                amount = (entry.quantity or Decimal(0)) * (entry.unit_price or Decimal(0))
                flows += amount if entry.type is T.BUY else -amount
        value = latest.amount + flows
    return PositionValue(
        instrument_id=instrument_id,
        kind=K.EURO_FUND,
        quantity=basis.quantity,
        total_cost=basis.total_cost,
        unit_cost=basis.unit_cost,
        price=None,
        price_date=None,
        value=value,
        estimated=estimated,
    )


def value_account(
    *,
    account_id: str,
    entries: Sequence[Entry],
    instruments: Mapping[str, InstrumentInfo],
    prices: Sequence[PricePoint],
    balances: Sequence[DeclaredBalanceRow],
    as_of: date,
    currency: str,
) -> AccountValue:
    """Valeur du compte `account_id` à `as_of`, dans la devise `currency`."""
    traded = {
        entry.instrument_id
        for entry in entries
        if entry.account_id == account_id
        and entry.instrument_id is not None
        and entry.type in {T.BUY, T.SELL}
        and not entry.voided
        and entry.trade_date <= as_of
    }
    declared = {b.instrument_id for b in balances if b.account_id == account_id}
    identifiers = sorted(identifier for identifier in traded | declared if identifier is not None)

    warnings: list[ValuationWarning] = []
    positions: list[PositionValue] = []
    for identifier in identifiers:
        if identifier not in instruments:
            raise KeyError(f"actif inconnu : {identifier}")
        info = instruments[identifier]
        if info.kind is K.EURO_FUND:
            position: PositionValue | None = _value_euro_fund(
                identifier, entries, balances, account_id, as_of, currency, warnings
            )
        elif info.kind is K.CASH:
            continue  # la trésorerie se calcule depuis les opérations, pas comme une position
        else:
            position = _value_priced(
                info.kind, identifier, entries, prices, account_id, as_of, currency, warnings
            )
        if position is not None:
            positions.append(position)

    cash = cash_balance(entries, account_id=account_id, as_of=as_of)
    total = cash + sum((p.value for p in positions if p.value is not None), Decimal(0))
    return AccountValue(
        account_id=account_id,
        as_of=as_of,
        currency=currency,
        cash=cash,
        positions=tuple(positions),
        total=total,
        estimated=any(p.estimated for p in positions),
        warnings=tuple(warnings),
    )
