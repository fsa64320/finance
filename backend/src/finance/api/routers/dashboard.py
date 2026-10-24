"""Routes du tableau de bord (contrat : tag `dashboard`)."""

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from finance.api import serializers
from finance.api.deps import get_db_session
from finance.services import dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    as_of: date | None = None, session: Session = Depends(get_db_session)
) -> dict[str, Any]:
    return serializers.dashboard_summary(dashboard.summary(session, as_of or date.today()))


@router.get("/series")
def series(
    period: Literal["1m", "3m", "1y", "5y", "all"] = "1y",
    session: Session = Depends(get_db_session),
) -> dict[str, Any]:
    return serializers.dashboard_series(dashboard.series(session, period, date.today()))


@router.get("/allocation")
def allocation(
    as_of: date | None = None, session: Session = Depends(get_db_session)
) -> dict[str, Any]:
    return serializers.dashboard_allocation(dashboard.allocation(session, as_of or date.today()))
