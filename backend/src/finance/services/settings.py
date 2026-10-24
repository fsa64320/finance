"""Réglages : devise de référence, récupération automatique des prix, rappel d'export (FR-029).

La récupération automatique des prix est **désactivée par défaut** (constitution, principe I) : rien
ne sort tant que l'utilisateur n'a pas fait un choix explicite, qu'il peut défaire à tout moment.
"""

import re
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.services.errors import FieldError, ValidationFailed

DEFAULT_REFERENCE_CURRENCY = "EUR"
DEFAULT_EXPORT_REMINDER_DAYS = 30
_CURRENCY = re.compile(r"[A-Z]{3}")

REFERENCE_CURRENCY_KEY = "reference_currency"
AUTO_FETCH_KEY = "auto_fetch_prices"
EXPORT_REMINDER_KEY = "export_reminder_days"
LAST_EXPORT_KEY = "last_export_at"


@dataclass(frozen=True)
class ExternalService:
    name: str
    purpose: str
    data_sent: str


# Affichée à l'utilisateur avant toute activation (FR-029) : ce qui sort, et rien d'autre.
EXTERNAL_SERVICES = (
    ExternalService(
        "BCE",
        "Taux de change de référence, contre l'euro",
        "Une requête sans paramètre : ni compte, ni montant, ni actif. Seules les devises que "
        "vous utilisez sont ensuite retenues, localement.",
    ),
    ExternalService(
        "Yahoo Finance",
        "Cours et valeurs liquidatives des actions, ETF et fonds",
        "Le ticker de chaque actif suivi automatiquement et une période grossière (5 jours, "
        "1 mois, 1 an ou tout). Aucune quantité, aucun montant, aucun nom de compte.",
    ),
    ExternalService(
        "OpenFIGI",
        "Recherche d'un ticker à partir d'un code ISIN, à votre demande",
        "Le code ISIN de l'actif concerné, rien d'autre.",
    ),
)


@dataclass(frozen=True)
class Settings:
    reference_currency: str
    auto_fetch_prices: bool
    export_reminder_days: int
    last_export_at: datetime | None


def _read(session: Session) -> dict[str, str]:
    return {row.key: row.value for row in session.scalars(sa.select(models.Setting))}


def get_settings(session: Session) -> Settings:
    values = _read(session)
    last = values.get(LAST_EXPORT_KEY)
    return Settings(
        reference_currency=values.get(REFERENCE_CURRENCY_KEY, DEFAULT_REFERENCE_CURRENCY),
        auto_fetch_prices=values.get(AUTO_FETCH_KEY, "false") == "true",
        export_reminder_days=int(values.get(EXPORT_REMINDER_KEY, DEFAULT_EXPORT_REMINDER_DAYS)),
        last_export_at=None if not last else datetime.fromisoformat(last),
    )


def _put(session: Session, key: str, value: str) -> None:
    row = session.get(models.Setting, key)
    if row is None:
        session.add(models.Setting(key=key, value=value))
    else:
        row.value = value


def update_settings(
    session: Session,
    *,
    reference_currency: str | None = None,
    auto_fetch_prices: bool | None = None,
    export_reminder_days: int | None = None,
) -> Settings:
    problems: list[FieldError] = []
    if reference_currency is not None and not _CURRENCY.fullmatch(reference_currency):
        problems.append(
            FieldError("reference_currency", "La devise est un code de trois lettres majuscules.")
        )
    if export_reminder_days is not None and export_reminder_days < 0:
        problems.append(
            FieldError("export_reminder_days", "Le délai de rappel ne peut pas être négatif.")
        )
    if problems:
        raise ValidationFailed(problems)
    if reference_currency is not None:
        _put(session, REFERENCE_CURRENCY_KEY, reference_currency)
    if auto_fetch_prices is not None:
        _put(session, AUTO_FETCH_KEY, "true" if auto_fetch_prices else "false")
    if export_reminder_days is not None:
        _put(session, EXPORT_REMINDER_KEY, str(export_reminder_days))
    session.flush()
    return get_settings(session)


def auto_fetch_enabled(session: Session) -> bool:
    return get_settings(session).auto_fetch_prices


def reference_currency(session: Session) -> str:
    return get_settings(session).reference_currency


def record_export(session: Session, at: datetime) -> None:
    """Retient la date du dernier export, pour le rappel périodique."""
    _put(session, LAST_EXPORT_KEY, at.isoformat())
    session.flush()
