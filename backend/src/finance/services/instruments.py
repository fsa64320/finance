"""Actifs : création, modification et liste (FR-002)."""

import re
from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import InstrumentKind, PriceMode
from finance.domain.isin import normalize_isin
from finance.services.errors import ConflictError, NotFoundError, ValidationFailed

_CURRENCY = re.compile(r"[A-Z]{3}")
_MANUAL_BY_DEFAULT = frozenset(
    {InstrumentKind.SCPI, InstrumentKind.FCPE, InstrumentKind.EURO_FUND, InstrumentKind.CASH}
)


def create_instrument(
    session: Session,
    *,
    kind: InstrumentKind,
    name: str,
    currency: str,
    isin: str | None = None,
    price_ticker: str | None = None,
    price_mode: PriceMode | None = None,
) -> models.Instrument:
    name = name.strip()
    if not name:
        raise ValidationFailed.single("name", "Le nom de l'actif est obligatoire.")
    if not _CURRENCY.fullmatch(currency):
        raise ValidationFailed.single(
            "currency", "La devise est un code de trois lettres majuscules."
        )
    code: str | None = None
    if isin is not None and isin.strip():
        try:
            code = normalize_isin(isin)
        except ValueError:
            raise ValidationFailed.single(
                "isin", "Code ISIN invalide : 12 caractères avec une clé de contrôle correcte."
            ) from None
        if session.scalar(sa.select(models.Instrument.id).where(models.Instrument.isin == code)):
            raise ConflictError(f"Un actif porte déjà l'ISIN {code}.")
    default_mode = PriceMode.MANUAL if kind in _MANUAL_BY_DEFAULT else PriceMode.AUTO
    instrument = models.Instrument(
        kind=kind,
        name=name,
        isin=code,
        currency=currency,
        price_ticker=price_ticker or None,
        price_mode=price_mode or default_mode,
    )
    session.add(instrument)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("Un actif porte déjà cet ISIN.") from error
    return instrument


def get_instrument(session: Session, instrument_id: str) -> models.Instrument:
    instrument = session.get(models.Instrument, instrument_id)
    if instrument is None:
        raise NotFoundError("Actif", instrument_id)
    return instrument


def list_instruments(session: Session) -> list[models.Instrument]:
    return list(session.scalars(sa.select(models.Instrument).order_by(models.Instrument.name)))


def update_instrument(
    session: Session, instrument_id: str, changes: Mapping[str, Any]
) -> models.Instrument:
    instrument = get_instrument(session, instrument_id)
    if "name" in changes:
        name = str(changes["name"]).strip()
        if not name:
            raise ValidationFailed.single("name", "Le nom de l'actif est obligatoire.")
        instrument.name = name
    if "price_ticker" in changes:
        ticker = changes["price_ticker"]
        instrument.price_ticker = (
            ticker.strip() if isinstance(ticker, str) and ticker.strip() else None
        )
    if "price_mode" in changes:
        instrument.price_mode = PriceMode(changes["price_mode"])
    session.flush()
    return instrument
