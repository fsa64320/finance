from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from finance.db.engine import open_database
from finance.db.migrate import upgrade
from finance.db.session import make_session_factory

# Mot de passe de test : valeur jetable, jamais utilisée hors de la suite de tests.
TEST_PASSWORD = "test-passphrase-not-a-secret"  # noqa: S105


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "finance.db"


@pytest.fixture
def engine(db_path: Path) -> Iterator[Engine]:
    """Base chiffrée vide (sans schéma)."""
    created = open_database(db_path, TEST_PASSWORD, create=True)
    yield created
    created.dispose()


@pytest.fixture
def migrated_engine(engine: Engine) -> Engine:
    """Base chiffrée avec le schéma complet (migrations appliquées)."""
    upgrade(engine)
    return engine


@pytest.fixture
def session(migrated_engine: Engine) -> Iterator[Session]:
    factory = make_session_factory(migrated_engine)
    with factory() as opened:
        yield opened


class FakeClock:
    """Horloge monotone contrôlée par les tests (secondes)."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
