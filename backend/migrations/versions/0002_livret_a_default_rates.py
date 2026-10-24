"""taux du Livret A livrés avec l'application

Historique des taux réglementaires du Livret A, pour que les intérêts soient estimés dès le premier
lancement (spec : taux paramétrables « initialisés à des valeurs courantes »). Valeurs à vérifier et
à compléter par la personne depuis l'écran des taux : l'application ne garantit pas leur actualité.
La table des taux est en ajout seul, donc le retour arrière ne retire pas ces lignes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

from finance.db.types import DecimalText, UtcDateTime

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (date d'effet, taux annuel en %), taux en vigueur du 1er février et du 1er août.
LIVRET_A_RATES = (
    (date(2020, 2, 1), Decimal("0.5")),
    (date(2022, 2, 1), Decimal("1")),
    (date(2022, 8, 1), Decimal("2")),
    (date(2023, 2, 1), Decimal("3")),
    (date(2025, 2, 1), Decimal("2.4")),
    (date(2025, 8, 1), Decimal("1.7")),
)


def upgrade() -> None:
    rate = sa.table(
        "rate",
        sa.column("id", sa.String),
        sa.column("kind", sa.String),
        sa.column("base", sa.String),
        sa.column("quote", sa.String),
        sa.column("effective_from", sa.Date),
        sa.column("value", DecimalText()),
        sa.column("source", sa.String),
        sa.column("recorded_at", UtcDateTime()),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        rate,
        [
            {
                "id": str(uuid4()),
                "kind": "LIVRET_A",
                "base": None,
                "quote": None,
                "effective_from": effective_from,
                "value": value,
                "source": "MANUAL",
                "recorded_at": now,
            }
            for effective_from, value in LIVRET_A_RATES
        ],
    )


def downgrade() -> None:
    # La table `rate` refuse DELETE (journal en ajout seul) : les lignes restent, sans effet.
    pass
