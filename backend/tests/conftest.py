from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
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


API_PASSWORD = "tulipe-bleue-47-horizon"  # noqa: S105 - valeur jetable des tests


@pytest.fixture
def authed_client(tmp_path: Path, clock: FakeClock) -> Iterator[TestClient]:
    """Client d'une instance initialisée avec une session ouverte."""
    from finance.config import Settings
    from finance.main import create_app

    settings = Settings(data_dir=tmp_path / "data", host="127.0.0.1", port=8000)
    with TestClient(create_app(settings, clock=clock), base_url="http://testserver") as client:
        response = client.post("/api/v1/auth/setup", json={"password": API_PASSWORD})
        assert response.status_code == 204
        yield client
