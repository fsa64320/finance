"""FR-028 et clarification 1 : sans le mot de passe, les données sont illisibles, sans récupération."""

import sqlite3
import threading
from pathlib import Path

import pytest
import sqlalchemy as sa

from finance.db import engine as engine_module
from finance.db.engine import (
    DatabaseExistsError,
    DatabaseNotFoundError,
    WeakCipherSettingsError,
    WrongPasswordError,
    cipher_settings,
    open_database,
)
from tests.conftest import TEST_PASSWORD

SQLITE_HEADER = b"SQLite format 3\x00"


def write_marker(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE marker (v TEXT)"))
        conn.execute(sa.text("INSERT INTO marker VALUES ('visible-seulement-avec-la-cle')"))


def read_marker(engine: sa.Engine) -> str:
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT v FROM marker")).scalar_one()


def test_file_is_not_readable_without_the_key(engine: sa.Engine, db_path: Path) -> None:
    write_marker(engine)
    engine.dispose()
    content = db_path.read_bytes()
    assert not content.startswith(SQLITE_HEADER)
    assert b"visible-seulement-avec-la-cle" not in content
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(db_path).execute("SELECT * FROM sqlite_master").fetchall()


def test_wrong_password_is_refused(engine: sa.Engine, db_path: Path) -> None:
    write_marker(engine)
    engine.dispose()
    with pytest.raises(WrongPasswordError):
        open_database(db_path, TEST_PASSWORD + "x")


def test_correct_password_reopens_the_data(engine: sa.Engine, db_path: Path) -> None:
    write_marker(engine)
    engine.dispose()
    reopened = open_database(db_path, TEST_PASSWORD)
    try:
        assert read_marker(reopened) == "visible-seulement-avec-la-cle"
    finally:
        reopened.dispose()


def test_no_recovery_path_exists_for_a_lost_password(engine: sa.Engine, db_path: Path) -> None:
    """Un oubli rend les données irrécupérables : aucune clé de secours n'ouvre le fichier."""
    write_marker(engine)
    engine.dispose()
    for guess in ("", "password", "0" * 12, TEST_PASSWORD.upper(), TEST_PASSWORD[:-1]):
        with pytest.raises((WrongPasswordError, ValueError)):
            open_database(db_path, guess)
    assert not [name for name in dir(engine_module) if "recover" in name.lower()]


@pytest.mark.parametrize(
    "password",
    [
        "p'a\"ss;word--",
        "mot de passe avec espaces",
        "émojis-🔒-et-accents-éàü",
        "a'; DROP TABLE x; --",
    ],
)
def test_special_characters_in_password_are_safe(tmp_path: Path, password: str) -> None:
    path = tmp_path / "special.db"
    created = open_database(path, password, create=True)
    write_marker(created)
    created.dispose()
    reopened = open_database(path, password)
    try:
        assert read_marker(reopened) == "visible-seulement-avec-la-cle"
    finally:
        reopened.dispose()


@pytest.mark.parametrize("password", ["", "with\x00nul"])
def test_unusable_passwords_are_rejected(tmp_path: Path, password: str) -> None:
    with pytest.raises(ValueError, match="mot de passe"):
        open_database(tmp_path / "x.db", password, create=True)


def test_create_refuses_to_overwrite_an_existing_database(engine: sa.Engine, db_path: Path) -> None:
    engine.dispose()
    with pytest.raises(DatabaseExistsError):
        open_database(db_path, TEST_PASSWORD, create=True)


def test_open_refuses_a_missing_database(tmp_path: Path) -> None:
    with pytest.raises(DatabaseNotFoundError):
        open_database(tmp_path / "absent.db", TEST_PASSWORD)
    assert not (tmp_path / "absent.db").exists()


def test_cipher_settings_are_the_sqlcipher4_defaults(engine: sa.Engine) -> None:
    assert cipher_settings(engine) == {
        "kdf_iter": 256000,
        "page_size": 4096,
        "hmac_algorithm": "HMAC_SHA512",
        "kdf_algorithm": "PBKDF2_HMAC_SHA512",
    }


def test_weaker_key_derivation_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_module, "KDF_ITER", 1000)
    with pytest.raises(WeakCipherSettingsError):
        open_database(tmp_path / "weak.db", TEST_PASSWORD, create=True)


def test_foreign_keys_are_enforced(engine: sa.Engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 1


def test_connections_from_several_threads_are_keyed(engine: sa.Engine) -> None:
    write_marker(engine)
    results: list[str] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(read_marker(engine))
        except BaseException as error:  # noqa: BLE001 - remonté dans le thread principal
            errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert results == ["visible-seulement-avec-la-cle"] * 6
