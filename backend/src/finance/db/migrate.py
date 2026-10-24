"""Application des migrations Alembic sur une base déjà ouverte (donc déverrouillée)."""

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


def alembic_config(connection: sa.Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def upgrade(engine: sa.Engine, revision: str = "head") -> None:
    """Amène le schéma à `revision` ; sans effet s'il y est déjà."""
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), revision)
