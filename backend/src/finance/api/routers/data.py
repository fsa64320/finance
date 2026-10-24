"""Routes d'export et de restauration (contrat : tag `data`)."""

from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from finance.api.deps import get_db_session
from finance.services import export

router = APIRouter(tags=["data"])


@router.get("/data/export")
def export_data(session: Session = Depends(get_db_session)) -> JSONResponse:
    body = export.export_data(session)
    day = str(body["exported_at"])[:10]
    return JSONResponse(
        body,
        headers={
            "Content-Disposition": f'attachment; filename="finance-export-{day}.json"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/data/restore",
    status_code=204,
    response_class=Response,
    responses={409: {"description": "L'instance n'est pas vide"}},
)
def restore_data(
    payload: dict[str, Any] = Body(...), session: Session = Depends(get_db_session)
) -> Response:
    export.restore_data(session, payload)
    return Response(status_code=204)
