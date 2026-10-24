"""Valeur d'un compte à une date : trésorerie + positions (research.md §8).

Tout est recalculé depuis le journal, les prix, les taux et les soldes déclarés. Quand un prix
manque, la position est valorisée à son prix de revient et signalée « estimée » (FR-025) ; un prix
ancien, un taux de change ancien ou des intérêts estimés le sont aussi. Un prix en devise étrangère
est converti au taux de la date de valorisation, ou signalé « non convertible » sans taux.

`value_priced` et `convert_amount` sont partagés avec le calcul par balayage de `series.py`, pour
que les deux chemins donnent exactement les mêmes valeurs.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from finance.domain.cost_basis import compute_cost_basis
from finance.domain.entries import Entry
from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind
from finance.domain.enums import TransactionType as T
from finance.domain.fx import FxTable
from finance.domain.ledger import cash_balance
from finance.domain.livret_a import LivretASchedule
from finance.domain.prices import PricePoint, is_stale, select_price

__all__ = [
    "PRICE_KIND_BY_INSTRUMENT",
    "AccountValue",
    "ConvertedAmount",
    "DeclaredBalanceRow",
    "InstrumentInfo",
    "PositionValue",
    "PricePoint",
    "PricedValue",
    "ValuationWarning",
    "convert_amount",
    "value_account",
    "value_priced",
]

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
    subscription_price: Decimal | None = None  # SCPI : dernier prix de souscription connu


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
    interest_estimate: Decimal = Decimal(0)  # Livret A : intérêts estimés inclus dans `total`


@dataclass(frozen=True)
class ConvertedAmount:
    value: Decimal | None  # None : non convertible
    code: str | None  # None, "non_convertible" ou "rate_stale"
    rate_date: date | None = None


def convert_amount(
    amount: Decimal, source: str, target: str, as_of: date, fx: FxTable | None
) -> ConvertedAmount:
    """Convertit `amount` ; signale un taux ancien (valeur estimée) ou absent (non convertible)."""
    if source == target:
        return ConvertedAmount(amount, None)
    conversion = None if fx is None else fx.convert(amount, source, target, as_of)
    if conversion is None:
        return ConvertedAmount(None, "non_convertible")
    code = "rate_stale" if conversion.is_stale(as_of) else None
    return ConvertedAmount(conversion.amount, code, conversion.rate_date)


def _rate_stale_message(rate_date: date | None) -> str:
    when = "" if rate_date is None else f" du {rate_date:%d/%m/%Y}"
    return f"Taux de change{when} ancien : la valeur est estimée."


@dataclass(frozen=True)
class PricedValue:
    value: Decimal | None
    estimated: bool
    warnings: tuple[tuple[str, str], ...]  # (code, message)


def value_priced(
    *,
    quantity: Decimal,
    total_cost: Decimal,
    price: PricePoint | None,
    currency: str,
    as_of: date,
    fx: FxTable | None,
) -> PricedValue:
    """Valeur d'une position détenue (`quantity` > 0) face au prix applicable `price`."""
    if price is None:
        return PricedValue(
            total_cost,
            True,
            (("price_missing", "Aucun prix connu : valorisé au prix de revient."),),
        )
    value: Decimal | None = quantity * price.value
    estimated = False
    warnings: list[tuple[str, str]] = []
    if price.currency != currency:
        converted = convert_amount(quantity * price.value, price.currency, currency, as_of, fx)
        if converted.value is None:
            return PricedValue(
                None,
                True,
                (
                    (
                        "non_convertible",
                        f"Prix en {price.currency} : conversion en {currency} indisponible.",
                    ),
                ),
            )
        value = converted.value
        if converted.code == "rate_stale":
            estimated = True
            warnings.append(("rate_stale", _rate_stale_message(converted.rate_date)))
    if is_stale(price, as_of):
        estimated = True
        warnings.append(
            (
                "price_stale",
                f"Prix ancien (du {price.price_date:%d/%m/%Y}) : la valeur est estimée.",
            )
        )
    return PricedValue(value, estimated, tuple(warnings))


def _value_priced_position(
    info: K,
    instrument_id: str,
    entries: Sequence[Entry],
    prices: Sequence[PricePoint],
    account_id: str,
    as_of: date,
    currency: str,
    fx: FxTable | None,
    warnings: list[ValuationWarning],
) -> PositionValue | None:
    basis = compute_cost_basis(
        entries, account_id=account_id, instrument_id=instrument_id, as_of=as_of
    )
    if basis.quantity == 0:
        return None
    price = select_price(prices, instrument_id, PRICE_KIND_BY_INSTRUMENT[info], as_of)
    subscription = (
        select_price(prices, instrument_id, PriceKind.SUBSCRIPTION, as_of)
        if info is K.SCPI
        else None
    )

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
            subscription_price=None if subscription is None else subscription.value,
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
    priced = value_priced(
        quantity=basis.quantity,
        total_cost=basis.total_cost,
        price=price,
        currency=currency,
        as_of=as_of,
        fx=fx,
    )
    warnings.extend(ValuationWarning(code, instrument_id, text) for code, text in priced.warnings)
    return result(priced.value, priced.estimated)


def _value_euro_fund(
    instrument_id: str,
    entries: Sequence[Entry],
    balances: Sequence[DeclaredBalanceRow],
    account_id: str,
    as_of: date,
    currency: str,
    fx: FxTable | None,
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
    else:
        converted = convert_amount(latest.amount, latest.currency, currency, as_of, fx)
        if converted.value is None:
            value, estimated = None, True
            warnings.append(
                ValuationWarning(
                    "non_convertible",
                    instrument_id,
                    f"Solde en {latest.currency} : conversion en {currency} indisponible.",
                )
            )
        else:
            if converted.code == "rate_stale":
                estimated = True
                warnings.append(
                    ValuationWarning(
                        "rate_stale", instrument_id, _rate_stale_message(converted.rate_date)
                    )
                )
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
            value = converted.value + flows
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
    fx: FxTable | None = None,
    livret: LivretASchedule | None = None,
) -> AccountValue:
    """Valeur du compte `account_id` à `as_of`, dans la devise `currency`.

    `fx` convertit les prix et soldes en devise étrangère ; `livret`, pour un Livret A, apporte les
    intérêts estimés.
    """
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
                identifier, entries, balances, account_id, as_of, currency, fx, warnings
            )
        elif info.kind is K.CASH:
            continue  # la trésorerie se calcule depuis les opérations, pas comme une position
        else:
            position = _value_priced_position(
                info.kind, identifier, entries, prices, account_id, as_of, currency, fx, warnings
            )
        if position is not None:
            positions.append(position)

    cash = cash_balance(entries, account_id=account_id, as_of=as_of)
    interest = Decimal(0)
    interest_estimated = False
    if livret is not None:
        estimate = livret.estimate_at(as_of)
        interest = estimate.total
        interest_estimated = interest != 0 or estimate.missing_rate_from is not None
        if estimate.missing_rate_from is not None:
            warnings.append(
                ValuationWarning(
                    "rate_missing",
                    None,
                    "Taux du Livret A manquant depuis le "
                    f"{estimate.missing_rate_from:%d/%m/%Y} : intérêts estimés incomplets.",
                )
            )
    total = cash + interest + sum((p.value for p in positions if p.value is not None), Decimal(0))
    return AccountValue(
        account_id=account_id,
        as_of=as_of,
        currency=currency,
        cash=cash,
        positions=tuple(positions),
        total=total,
        estimated=interest_estimated or any(p.estimated for p in positions),
        warnings=tuple(warnings),
        interest_estimate=interest,
    )
