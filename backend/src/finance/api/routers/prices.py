"""Routes des prix et de leur mise à jour (contrat : tag `prices`)."""

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from finance.api import serializers
from finance.api.deps import get_db_session
from finance.api.schemas import LivretARateInput, PriceInput
from finance.prices.base import Providers
from finance.services import prices, rates

router = APIRouter(tags=["prices"])


def get_providers(request: Request) -> Providers:
    providers: Providers = request.app.state.providers
    return providers


@router.get("/prices")
def list_prices(
    instrument_id: UUID,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    session: Session = Depends(get_db_session),
) -> list[dict[str, Any]]:
    rows = prices.list_prices(session, str(instrument_id), date_from=date_from, date_to=date_to)
    return [serializers.price(row) for row in rows]


@router.post("/prices", status_code=201)
def add_price(body: PriceInput, session: Session = Depends(get_db_session)) -> dict[str, Any]:
    row = prices.add_manual_price(
        session,
        instrument_id=str(body.instrument_id),
        price_date=body.price_date,
        kind=body.kind,
        value=body.value,
        currency=body.currency,
        today=date.today(),
    )
    return serializers.price(row)


@router.post("/prices/refresh")
def refresh_prices(
    session: Session = Depends(get_db_session), providers: Providers = Depends(get_providers)
) -> dict[str, Any]:
    return serializers.refresh_result(prices.refresh(session, providers, date.today()))


@router.get("/rates/livret-a")
def list_livret_rates(session: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    return [serializers.livret_rate(row) for row in rates.list_livret_a_rates(session)]


@router.post("/rates/livret-a", status_code=201)
def add_livret_rate(
    body: LivretARateInput, session: Session = Depends(get_db_session)
) -> dict[str, Any]:
    row = rates.add_livret_a_rate(session, effective_from=body.effective_from, value=body.value)
    return serializers.livret_rate(row)
