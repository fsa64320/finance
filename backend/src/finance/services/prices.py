"""Prix : saisie manuelle, liste et mise à jour depuis les sources externes (FR-011 à FR-013).

Les sources ne reçoivent que des tickers, des ISIN et des devises. Elles sont interrogées
uniquement si la récupération automatique a été activée ; sinon rien ne sort. Une source qui échoue
ne modifie aucune donnée : l'application garde les derniers prix connus et le signale.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import InstrumentKind as K
from finance.domain.enums import PriceKind, PriceMode, PriceSource, RateKind, RateSource
from finance.domain.fx import PIVOT
from finance.prices.base import ProviderError, Providers, TickerSuggestion
from finance.services import settings as settings_service
from finance.services.errors import (
    ConflictError,
    ExternalSourceError,
    FieldError,
    NotFoundError,
    ValidationFailed,
)

ALLOWED_KINDS: dict[K, tuple[PriceKind, ...]] = {
    K.EQUITY: (PriceKind.MARKET,),
    K.ETF: (PriceKind.MARKET,),
    K.FUND: (PriceKind.NAV,),
    K.FCPE: (PriceKind.NAV,),
    K.SCPI: (PriceKind.SUBSCRIPTION, PriceKind.REDEMPTION),
}
_KIND_LABELS = {
    PriceKind.MARKET: "cours",
    PriceKind.NAV: "valeur liquidative",
    PriceKind.SUBSCRIPTION: "prix de souscription",
    PriceKind.REDEMPTION: "prix de retrait",
}


@dataclass(frozen=True)
class SourceResult:
    source: str
    status: str  # ok, partial, failed ou disabled
    updated: int = 0
    message: str | None = None


def list_prices(
    session: Session, instrument_id: str, *, date_from: date | None, date_to: date | None
) -> list[models.Price]:
    if session.get(models.Instrument, instrument_id) is None:
        raise ValidationFailed.single("instrument_id", "Actif introuvable.")
    statement = sa.select(models.Price).where(models.Price.instrument_id == instrument_id)
    if date_from is not None:
        statement = statement.where(models.Price.price_date >= date_from)
    if date_to is not None:
        statement = statement.where(models.Price.price_date <= date_to)
    statement = statement.order_by(models.Price.price_date, models.Price.recorded_at)
    return list(session.scalars(statement))


def add_manual_price(
    session: Session,
    *,
    instrument_id: str,
    price_date: date,
    kind: PriceKind,
    value: Decimal,
    currency: str,
    today: date,
) -> models.Price:
    instrument = session.get(models.Instrument, instrument_id)
    if instrument is None:
        raise ValidationFailed.single("instrument_id", "Actif introuvable.")
    problems: list[FieldError] = []
    allowed = ALLOWED_KINDS.get(instrument.kind)
    if allowed is None:
        problems.append(
            FieldError("kind", "Cet actif se valorise par un solde déclaré, pas par un prix.")
        )
    elif kind not in allowed:
        wanted = " ou ".join(_KIND_LABELS[item] for item in allowed)
        problems.append(FieldError("kind", f"Pour cet actif, saisissez un {wanted}."))
    if not value.is_finite() or value <= 0:
        problems.append(FieldError("value", "Le prix doit être strictement positif."))
    if price_date > today:
        problems.append(FieldError("price_date", "La date du prix ne peut pas être dans le futur."))
    if len(currency) != 3 or not currency.isupper():
        problems.append(
            FieldError("currency", "La devise est un code de trois lettres majuscules.")
        )
    if problems:
        raise ValidationFailed(problems)
    row = models.Price(
        instrument_id=instrument_id,
        price_date=price_date,
        kind=kind,
        value=value,
        currency=currency,
        source=PriceSource.MANUAL,
    )
    session.add(row)
    session.flush()
    return row


def _period_for(last: date | None, today: date) -> str:
    """Période grossière demandée à la source : elle ne révèle rien des opérations."""
    if last is None:
        return "max"
    age = (today - last).days
    if age <= 5:
        return "5d"
    if age <= 25:
        return "1mo"
    if age <= 350:
        return "1y"
    return "max"


def _refresh_rates(session: Session, providers: Providers) -> SourceResult:
    currencies = (
        set(session.scalars(sa.select(models.Instrument.currency)))
        | set(session.scalars(sa.select(models.Account.currency)))
        | {settings_service.reference_currency(session)}
    )
    wanted = currencies - {PIVOT}
    if not wanted:
        return SourceResult("ecb", "ok", 0)
    try:
        fetched = providers.rates.fetch()
    except ProviderError as error:
        return SourceResult("ecb", "failed", 0, str(error))
    known = {
        (row.quote, row.effective_from, row.value)
        for row in session.scalars(sa.select(models.Rate).where(models.Rate.kind == RateKind.FX))
    }
    added = 0
    with session.begin_nested():
        for rate in fetched:
            if rate.quote not in wanted or (rate.quote, rate.rate_date, rate.value) in known:
                continue
            session.add(
                models.Rate(
                    kind=RateKind.FX,
                    base=PIVOT,
                    quote=rate.quote,
                    effective_from=rate.rate_date,
                    value=rate.value,
                    source=RateSource.ECB,
                )
            )
            added += 1
    return SourceResult("ecb", "ok", added)


def _refresh_prices(session: Session, providers: Providers, today: date) -> SourceResult:
    instruments = [
        item
        for item in session.scalars(
            sa.select(models.Instrument).where(
                models.Instrument.price_mode == PriceMode.AUTO,
                models.Instrument.price_ticker.is_not(None),
            )
        )
        if item.kind in ALLOWED_KINDS
        and ALLOWED_KINDS[item.kind][0] in (PriceKind.MARKET, PriceKind.NAV)
        and item.price_ticker
    ]
    if not instruments:
        return SourceResult("yahoo", "ok", 0)

    existing = defaultdict(set)
    manual_days: set[tuple[str, PriceKind, date]] = set()
    last_seen: dict[str, date] = {}
    for row in session.scalars(sa.select(models.Price)):
        existing[row.instrument_id].add((row.kind, row.price_date, row.value))
        if row.source is PriceSource.MANUAL:
            manual_days.add((row.instrument_id, row.kind, row.price_date))
        if row.source is PriceSource.PROVIDER:
            last_seen[row.instrument_id] = max(
                last_seen.get(row.instrument_id, row.price_date), row.price_date
            )

    by_ticker: dict[str, list[models.Instrument]] = defaultdict(list)
    for item in instruments:
        by_ticker[str(item.price_ticker)].append(item)
    by_period: dict[str, list[str]] = defaultdict(list)
    for ticker, owners in by_ticker.items():
        last = min((last_seen[o.id] for o in owners if o.id in last_seen), default=None)
        if any(o.id not in last_seen for o in owners):
            last = None
        by_period[_period_for(last, today)].append(ticker)

    added = 0
    failed: list[str] = []
    try:
        with session.begin_nested():
            for period, tickers in by_period.items():
                batch = providers.prices.fetch(tickers, period=period)
                failed.extend(batch.failed)
                for ticker, prices in batch.found.items():
                    for owner in by_ticker[ticker]:
                        kind = ALLOWED_KINDS[owner.kind][0]
                        for price in prices:
                            if price.value <= 0 or price.price_date > today:
                                continue
                            known = (kind, price.price_date, price.value)
                            if known in existing[owner.id]:
                                continue
                            if (owner.id, kind, price.price_date) in manual_days:
                                continue
                            session.add(
                                models.Price(
                                    instrument_id=owner.id,
                                    price_date=price.price_date,
                                    kind=kind,
                                    value=price.value,
                                    currency=price.currency,
                                    source=PriceSource.PROVIDER,
                                )
                            )
                            existing[owner.id].add(known)
                            added += 1
    except ProviderError as error:
        return SourceResult("yahoo", "failed", 0, str(error))
    if failed:
        names = ", ".join(sorted(set(failed)))
        return SourceResult("yahoo", "partial", added, f"Pas de cours pour : {names}.")
    return SourceResult("yahoo", "ok", added)


def refresh(session: Session, providers: Providers, today: date) -> list[SourceResult]:
    """Met à jour taux et cours ; sans effet (et sans requête) si la récupération est désactivée."""
    if not settings_service.auto_fetch_enabled(session):
        return [SourceResult("ecb", "disabled"), SourceResult("yahoo", "disabled")]
    return [_refresh_rates(session, providers), _refresh_prices(session, providers, today)]


def suggest_tickers(
    session: Session, providers: Providers, instrument_id: str
) -> list[TickerSuggestion]:
    """Tickers possibles pour l'ISIN de l'actif ; seul l'ISIN part, à la demande de la personne."""
    instrument = session.get(models.Instrument, instrument_id)
    if instrument is None:
        raise NotFoundError("Actif", instrument_id)
    if not settings_service.auto_fetch_enabled(session):
        raise ConflictError(
            "La récupération automatique est désactivée : activez-la dans les réglages pour "
            "chercher un ticker."
        )
    if not instrument.isin:
        raise ValidationFailed.single("isin", "Cet actif n'a pas de code ISIN à rechercher.")
    try:
        return providers.tickers.suggest(instrument.isin)
    except ProviderError as error:
        raise ExternalSourceError(str(error)) from error
