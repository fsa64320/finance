"""Service d'authentification : états, métadonnées, nettoyage en cas d'échec (T027, T028)."""

import json
import os
import stat
from pathlib import Path

import pytest
from sqlalchemy import text

from finance.auth import metadata
from finance.auth.errors import (
    AlreadyInitializedError,
    InvalidCredentialsError,
    LockedError,
    NotInitializedError,
    TooManyAttemptsError,
)
from finance.auth.passwords import PasswordPolicyError
from finance.auth.service import AuthService
from finance.config import Settings
from tests.conftest import FakeClock

PASSWORD = "tulipe-bleue-47-horizon"  # noqa: S105 - valeur jetable des tests
OTHER = "autre-mot-de-passe-91"


def make_service(tmp_path: Path, clock: FakeClock) -> AuthService:
    settings = Settings(data_dir=tmp_path / "data", host="127.0.0.1", port=8000)
    return AuthService(settings, clock=clock)


def test_a_new_instance_is_uninitialized(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    assert service.state(None) == "uninitialized"
    assert not metadata.is_initialized(tmp_path / "data")
    with pytest.raises(NotInitializedError):
        service.unlock(PASSWORD)


def test_setup_creates_the_database_the_metadata_and_a_session(
    tmp_path: Path, clock: FakeClock
) -> None:
    service = make_service(tmp_path, clock)
    token = service.setup(PASSWORD)
    assert service.state(token) == "unlocked"
    assert service.is_open
    with service.engine().connect() as connection:
        tables = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).scalars()
        assert "account" in set(tables)
    assert metadata.is_initialized(tmp_path / "data")


def test_metadata_describes_the_cipher_without_any_secret(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    service.setup(PASSWORD)
    path = metadata.metadata_path(tmp_path / "data")
    content = json.loads(path.read_text(encoding="utf-8"))
    assert content["format"] == 1
    assert content["cipher"]["kdf_iter"] == 256000
    assert PASSWORD not in path.read_text(encoding="utf-8")
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE((tmp_path / "data").stat().st_mode) == 0o700


def test_setup_twice_is_refused(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    service.setup(PASSWORD)
    with pytest.raises(AlreadyInitializedError):
        service.setup(OTHER)


def test_existing_database_without_metadata_is_never_overwritten(
    tmp_path: Path, clock: FakeClock
) -> None:
    first = make_service(tmp_path, clock)
    first.setup(PASSWORD)
    first.shutdown()
    metadata.metadata_path(tmp_path / "data").unlink()
    second = make_service(tmp_path, clock)
    with pytest.raises(AlreadyInitializedError):
        second.setup(OTHER)
    assert second.state(None) == "locked"


def test_weak_password_creates_nothing(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    with pytest.raises(PasswordPolicyError):
        service.setup("motdepasse123")
    assert not (tmp_path / "data" / "finance.db").exists()
    assert service.state(None) == "uninitialized"


def test_failed_migration_leaves_no_half_initialized_instance(
    tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object, **__: object) -> None:
        raise RuntimeError("migration cassée")

    monkeypatch.setattr("finance.auth.service.upgrade", broken)
    service = make_service(tmp_path, clock)
    with pytest.raises(RuntimeError, match="migration cassée"):
        service.setup(PASSWORD)
    assert not (tmp_path / "data" / "finance.db").exists()
    assert not metadata.is_initialized(tmp_path / "data")
    assert service.state(None) == "uninitialized"
    assert not service.is_open


def test_lock_closes_the_database(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    token = service.setup(PASSWORD)
    service.lock(token)
    assert not service.is_open
    assert service.state(token) == "locked"
    with pytest.raises(LockedError):
        service.engine()


def test_unlock_with_a_second_session_keeps_the_first(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    first = service.setup(PASSWORD)
    second = service.unlock(PASSWORD)
    assert first != second
    assert service.state(first) == "unlocked"
    assert service.state(second) == "unlocked"


def test_expired_last_session_closes_the_database(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    token = service.setup(PASSWORD)
    clock.advance(31 * 60)
    assert service.state(token) == "locked"
    assert not service.is_open


def test_wrong_password_counts_and_blocks(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    service.lock(service.setup(PASSWORD))
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            service.unlock(OTHER)
    with pytest.raises(TooManyAttemptsError) as blocked:
        service.unlock(PASSWORD)
    assert blocked.value.retry_after == 15


def test_shutdown_disposes_the_engine(tmp_path: Path, clock: FakeClock) -> None:
    service = make_service(tmp_path, clock)
    service.setup(PASSWORD)
    service.shutdown()
    assert not service.is_open
