"""Routes des réglages (contrat : tag `settings`)."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from finance.api import serializers
from finance.api.deps import get_db_session
from finance.api.schemas import SettingsPatch
from finance.services import settings as settings_service

router = APIRouter(tags=["settings"])


@router.get("/settings")
def read_settings(session: Session = Depends(get_db_session, scope="function")) -> dict[str, Any]:
    return serializers.settings_body(settings_service.get_settings(session))


@router.patch("/settings")
def patch_settings(
    body: SettingsPatch, session: Session = Depends(get_db_session, scope="function")
) -> dict[str, Any]:
    changed = settings_service.update_settings(
        session,
        reference_currency=body.reference_currency,
        auto_fetch_prices=body.auto_fetch_prices,
        export_reminder_days=body.export_reminder_days,
    )
    return serializers.settings_body(changed)
