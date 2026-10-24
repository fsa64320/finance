"""Routes d'import CSV et de paramétrages (contrat : tag `imports`)."""

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from finance.api import serializers
from finance.api.deps import get_db_session
from finance.api.schemas import ImportCommitInput, ImportMappingInput
from finance.services import import_mappings, imports
from finance.services.errors import ValidationFailed
from finance.services.imports import PreviewState, PreviewStore, Resolution

router = APIRouter(tags=["imports"])


def get_previews(request: Request) -> PreviewStore[PreviewState]:
    store: PreviewStore[PreviewState] = request.app.state.import_previews
    return store


@router.get("/import-mappings")
def list_import_mappings(session: Session = Depends(get_db_session)) -> list[dict[str, Any]]:
    return [serializers.import_mapping(row) for row in import_mappings.list_mappings(session)]


@router.post(
    "/import-mappings",
    status_code=201,
    responses={409: {"description": "Nom de paramétrage déjà utilisé"}},
)
def create_import_mapping(
    body: ImportMappingInput, session: Session = Depends(get_db_session)
) -> dict[str, Any]:
    mapping = import_mappings.create_mapping(
        session,
        import_mappings.MappingData(
            name=body.name,
            delimiter=body.delimiter,
            encoding=body.encoding,
            date_format=body.date_format,
            decimal_separator=body.decimal_separator,
            columns=body.columns,
        ),
    )
    return serializers.import_mapping(mapping)


def _columns(raw: str | None) -> dict[str, str] | None:
    if raw is None or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    if not isinstance(parsed, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()
    ):
        raise ValidationFailed.single(
            "columns", "La correspondance des colonnes est un objet JSON {donnée: colonne}."
        )
    return parsed


@router.post("/imports/preview")
def preview_import(
    file: UploadFile = File(...),
    account_id: UUID = Form(...),
    mapping_id: UUID | None = Form(default=None),
    delimiter: str | None = Form(default=None, max_length=1),
    encoding: str | None = Form(default=None),
    date_format: str | None = Form(default=None),
    decimal_separator: str | None = Form(default=None, pattern=r"^[,.]$"),
    columns: str | None = Form(default=None),
    session: Session = Depends(get_db_session),
    store: PreviewStore[PreviewState] = Depends(get_previews),
) -> dict[str, Any]:
    # Une octet de plus que la limite suffit à la détecter sans lire un fichier démesuré.
    content = file.file.read(imports.MAX_FILE_BYTES + 1)
    result = imports.preview(
        session,
        store,
        account_id=str(account_id),
        file_name=file.filename or "import.csv",
        content=content,
        mapping_id=None if mapping_id is None else str(mapping_id),
        delimiter=delimiter,
        encoding=encoding,
        date_format=date_format,
        decimal_separator=decimal_separator,
        columns=_columns(columns),
    )
    return serializers.import_preview(result)


@router.post(
    "/imports/commit",
    status_code=201,
    responses={404: {"description": "Aperçu introuvable ou expiré"}},
)
def commit_import(
    body: ImportCommitInput,
    session: Session = Depends(get_db_session),
    store: PreviewStore[PreviewState] = Depends(get_previews),
) -> dict[str, Any]:
    resolutions = [
        Resolution(
            key=item.key,
            action=item.action,
            kind=item.kind,
            instrument_id=None if item.instrument_id is None else str(item.instrument_id),
        )
        for item in body.instrument_resolutions or []
    ]
    outcome = imports.commit(
        session,
        store,
        preview_id=body.preview_id,
        confirm_rejected=body.confirm_rejected,
        resolutions=resolutions,
        save_mapping_as=body.save_mapping_as,
    )
    return serializers.import_result(outcome)
