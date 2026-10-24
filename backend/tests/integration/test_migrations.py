"""T026 : la migration initiale produit exactement le schéma des modèles, déclencheurs compris."""

import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from finance.db.append_only import PROTECTED_TABLES
from finance.db.migrate import upgrade
from finance.db.models import Base


def test_upgrade_records_the_head_revision(migrated_engine: sa.Engine) -> None:
    with migrated_engine.connect() as conn:
        version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0001"


def test_upgrade_is_idempotent(migrated_engine: sa.Engine) -> None:
    upgrade(migrated_engine)
    upgrade(migrated_engine)


def test_migrated_schema_matches_the_models(migrated_engine: sa.Engine) -> None:
    with migrated_engine.connect() as conn:
        differences = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert differences == []


def test_append_only_triggers_exist_for_every_protected_table(migrated_engine: sa.Engine) -> None:
    with migrated_engine.connect() as conn:
        triggers = set(
            conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).scalars()
        )
    expected = {
        f"{table}_no_{action}" for table in PROTECTED_TABLES for action in ("update", "delete")
    }
    assert expected <= triggers


def test_mutable_tables_have_no_triggers(migrated_engine: sa.Engine) -> None:
    with migrated_engine.connect() as conn:
        tables = set(
            conn.execute(
                sa.text("SELECT tbl_name FROM sqlite_master WHERE type = 'trigger'")
            ).scalars()
        )
    assert tables <= set(PROTECTED_TABLES)
