"""Taux : table datée du Livret A (modifiable) et taux de change de la BCE (FR-009, FR-025).

Les tables sont en ajout seul : corriger un taux ajoute une ligne, et la plus récente saisie à une
même date d'effet fait foi.
"""

from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from finance.db import models
from finance.domain.enums import RateKind, RateSource
from finance.services.errors import ValidationFailed


def list_livret_a_rates(session: Session) -> list[models.Rate]:
    """Un taux par date d'effet (le plus récemment saisi), du plus ancien au plus récent."""
    rows = session.scalars(
        sa.select(models.Rate)
        .where(models.Rate.kind == RateKind.LIVRET_A)
        .order_by(models.Rate.effective_from, models.Rate.recorded_at)
    )
    latest: dict[date, models.Rate] = {}
    for row in rows:
        latest[row.effective_from] = row
    return [latest[key] for key in sorted(latest)]


def add_livret_a_rate(session: Session, *, effective_from: date, value: Decimal) -> models.Rate:
    if not value.is_finite() or value < 0 or value > 100:
        raise ValidationFailed.single("value", "Le taux est un pourcentage entre 0 et 100.")
    row = models.Rate(
        kind=RateKind.LIVRET_A,
        base=None,
        quote=None,
        effective_from=effective_from,
        value=value,
        source=RateSource.MANUAL,
    )
    session.add(row)
    session.flush()
    return row
