"""Routes des actifs (contrat : tag `instruments`)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from finance.api import serializers
from finance.api.deps import get_db_session
from finance.api.routers.prices import get_providers
from finance.api.schemas import InstrumentInput, InstrumentPatch
from finance.domain.enums import PriceMode
from finance.prices.base import Providers
from finance.services import instruments, prices

router = APIRouter(tags=["instruments"])


@router.get("/instruments")
def list_instruments(session: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    return [serializers.instrument(row) for row in instruments.list_instruments(session)]


@router.post("/instruments", status_code=201, responses={409: {"description": "ISIN déjà utilisé"}})
def create_instrument(
    body: InstrumentInput, session: Session = Depends(get_db_session)
) -> dict[str, Any]:
    row = instruments.create_instrument(
        session,
        kind=body.kind,
        name=body.name,
        currency=body.currency,
        isin=body.isin,
        price_ticker=body.price_ticker,
        price_mode=None if body.price_mode is None else PriceMode(body.price_mode),
    )
    return serializers.instrument(row)


@router.patch("/instruments/{instrumentId}", responses={404: {"description": "Actif introuvable"}})
def patch_instrument(
    instrumentId: UUID,
    body: InstrumentPatch,
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    changes = body.model_dump(exclude_unset=True)
    return serializers.instrument(
        instruments.update_instrument(session, str(instrumentId), changes)
    )


@router.post(
    "/instruments/{instrumentId}/ticker-suggestions",
    responses={
        404: {"description": "Actif introuvable"},
        409: {"description": "Récupération automatique désactivée"},
        502: {"description": "Source externe indisponible"},
    },
)
def ticker_suggestions(
    instrumentId: UUID,
    session: Session = Depends(get_db_session),
    providers: Providers = Depends(get_providers),
) -> list[dict[str, str]]:
    found = prices.suggest_tickers(session, providers, str(instrumentId))
    return [{"ticker": s.ticker, "exchange": s.exchange, "name": s.name} for s in found]
