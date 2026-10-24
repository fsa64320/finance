"""Paramétrages d'import par établissement : colonnes, séparateurs, encodage (FR-019)."""

import codecs
from dataclasses import dataclass
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.importers.csv_generic import FIELDS
from finance.services.errors import ConflictError, FieldError, NotFoundError, ValidationFailed

REQUIRED_COLUMNS = ("trade_date", "type")


@dataclass(frozen=True)
class MappingData:
    name: str
    delimiter: str
    encoding: str
    date_format: str
    decimal_separator: str
    columns: dict[str, str]


def _problems(data: MappingData) -> list[FieldError]:
    problems: list[FieldError] = []
    if not data.name.strip():
        problems.append(FieldError("name", "Le nom du paramétrage est obligatoire."))
    if len(data.delimiter) != 1:
        problems.append(FieldError("delimiter", "Le séparateur est un seul caractère."))
    if data.decimal_separator not in (",", "."):
        problems.append(
            FieldError("decimal_separator", "Le séparateur décimal est une virgule ou un point.")
        )
    try:
        codecs.lookup(data.encoding)
    except LookupError:
        problems.append(FieldError("encoding", f"Encodage inconnu : « {data.encoding} »."))
    sample = date(2024, 1, 31)
    try:
        readable = "%" in data.date_format and sample.strftime(data.date_format)
        if not readable or _parse(readable, data.date_format) != sample:
            raise ValueError
    except ValueError:
        problems.append(
            FieldError("date_format", f"Format de date illisible : « {data.date_format} ».")
        )
    unknown = sorted(set(data.columns) - set(FIELDS))
    if unknown:
        problems.append(FieldError("columns", f"Donnée inconnue : « {unknown[0]} »."))
    missing = [key for key in REQUIRED_COLUMNS if not data.columns.get(key, "").strip()]
    if missing:
        problems.append(
            FieldError("columns", "Indiquez au moins la colonne de la date et celle du type.")
        )
    return problems


def _parse(text: str, fmt: str) -> date:
    from datetime import datetime

    return datetime.strptime(text, fmt).date()


def list_mappings(session: Session) -> list[models.ImportMapping]:
    return list(
        session.scalars(sa.select(models.ImportMapping).order_by(models.ImportMapping.name))
    )


def get_mapping(session: Session, mapping_id: str) -> models.ImportMapping:
    mapping = session.get(models.ImportMapping, mapping_id)
    if mapping is None:
        raise NotFoundError("Paramétrage", mapping_id)
    return mapping


def create_mapping(session: Session, data: MappingData) -> models.ImportMapping:
    problems = _problems(data)
    if problems:
        raise ValidationFailed(problems)
    name = data.name.strip()
    if session.scalar(sa.select(models.ImportMapping.id).where(models.ImportMapping.name == name)):
        raise ConflictError(f"Un paramétrage porte déjà le nom « {name} ».")
    mapping = models.ImportMapping(
        name=name,
        delimiter=data.delimiter,
        encoding=data.encoding,
        date_format=data.date_format,
        decimal_separator=data.decimal_separator,
        columns={key: value.strip() for key, value in data.columns.items()},
    )
    session.add(mapping)
    session.flush()
    return mapping


def ensure_name_free(session: Session, name: str) -> None:
    if not name.strip():
        raise ValidationFailed.single("save_mapping_as", "Le nom du paramétrage est obligatoire.")
    if session.scalar(
        sa.select(models.ImportMapping.id).where(models.ImportMapping.name == name.strip())
    ):
        raise ConflictError(f"Un paramétrage porte déjà le nom « {name.strip()} ».")


def suggest_mapping(session: Session, headers: list[str]) -> models.ImportMapping | None:
    """Paramétrage dont toutes les colonnes figurent dans l'en-tête du fichier (FR-019)."""
    present = {header.strip() for header in headers}
    for mapping in list_mappings(session):
        wanted = {value.strip() for value in mapping.columns.values() if value}
        if wanted and wanted <= present:
            return mapping
    return None
