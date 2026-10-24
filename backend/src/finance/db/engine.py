"""Ouverture de la base SQLite chiffrée par SQLCipher (FR-028).

Le mot de passe est la clé : l'ouvrir correctement prouve que le mot de passe est bon. Il n'existe
aucun mécanisme de récupération (clarification 1) : un oubli rend les données illisibles.
"""

import threading
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlcipher3 import dbapi2 as sqlcipher

# Paramètres SQLCipher 4, fixés explicitement pour ne pas dépendre des valeurs par défaut de la
# bibliothèque (et refusés si elles sont plus faibles que le minimum ci-dessous).
KDF_ITER = 256_000
MIN_KDF_ITER = 256_000
PAGE_SIZE = 4096
HMAC_ALGORITHM = "HMAC_SHA512"
KDF_ALGORITHM = "PBKDF2_HMAC_SHA512"


class WrongPasswordError(Exception):
    """Le mot de passe ne déchiffre pas la base (ou le fichier n'est pas une base chiffrée)."""


class DatabaseExistsError(Exception):
    """Création refusée : une base existe déjà à cet emplacement."""


class DatabaseNotFoundError(Exception):
    """Ouverture refusée : aucune base à cet emplacement."""


class WeakCipherSettingsError(Exception):
    """Les paramètres de chiffrement de la connexion sont plus faibles que le minimum exigé."""


def _check_password(password: str) -> None:
    if not password or "\x00" in password:
        raise ValueError("mot de passe vide ou contenant un octet nul")


def _quote(password: str) -> str:
    # PRAGMA n'accepte pas de paramètre lié : on échappe les apostrophes du littéral SQL.
    return "'" + password.replace("'", "''") + "'"


def _pragma(connection: Any, name: str) -> Any:
    row = connection.execute(f"PRAGMA {name}").fetchone()
    return None if row is None else row[0]


def _read_cipher_settings(connection: Any) -> dict[str, Any]:
    return {
        "kdf_iter": int(_pragma(connection, "kdf_iter")),
        "page_size": int(_pragma(connection, "cipher_page_size")),
        "hmac_algorithm": _pragma(connection, "cipher_hmac_algorithm"),
        "kdf_algorithm": _pragma(connection, "cipher_kdf_algorithm"),
    }


# L'initialisation de SQLCipher (et d'OpenSSL en dessous) n'est pas sûre quand plusieurs threads
# ouvrent une connexion au même moment : un plantage (segmentation fault) a été observé en CI. Les
# ouvertures sont donc sérialisées ; elles sont brèves, une fois les connexions du pool créées.
_CONNECT_LOCK = threading.Lock()


def _connect(path: Path, password: str) -> Any:
    with _CONNECT_LOCK:
        return _open_connection(path, password)


def _open_connection(path: Path, password: str) -> Any:
    connection = sqlcipher.connect(str(path), check_same_thread=False)
    try:
        connection.execute(f"PRAGMA key = {_quote(password)}")
        connection.execute(f"PRAGMA kdf_iter = {KDF_ITER}")
        connection.execute(f"PRAGMA cipher_page_size = {PAGE_SIZE}")
        connection.execute(f"PRAGMA cipher_hmac_algorithm = {HMAC_ALGORITHM}")
        connection.execute(f"PRAGMA cipher_kdf_algorithm = {KDF_ALGORITHM}")
        settings = _read_cipher_settings(connection)
        if settings["kdf_iter"] < MIN_KDF_ITER:
            raise WeakCipherSettingsError(
                f"dérivation de clé trop faible : {settings['kdf_iter']} itérations "
                f"(minimum {MIN_KDF_ITER})"
            )
        try:
            connection.execute("SELECT count(*) FROM sqlite_master").fetchall()
        except sqlcipher.DatabaseError as error:
            raise WrongPasswordError("mot de passe incorrect ou base illisible") from error
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
    except BaseException:
        connection.close()
        raise
    return connection


def open_database(path: Path, password: str, *, create: bool = False) -> sa.Engine:
    """Ouvre la base chiffrée à `path`, ou la crée si `create` est vrai.

    Le mot de passe est conservé dans la fermeture du `creator` : chaque connexion du pool doit
    ressaisir la clé. Il ne quitte jamais le processus.
    """
    _check_password(password)
    path = Path(path)
    if create:
        if path.exists():
            raise DatabaseExistsError(f"une base existe déjà : {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.exists():
        raise DatabaseNotFoundError(f"aucune base : {path}")

    engine = sa.create_engine(
        "sqlite://",
        module=sqlcipher,
        creator=lambda: _connect(path, password),
    )
    try:
        with engine.connect():
            pass
    except BaseException:
        engine.dispose()
        if create:
            path.unlink(missing_ok=True)
        raise
    return engine


def cipher_settings(engine: sa.Engine) -> dict[str, Any]:
    """Paramètres de chiffrement effectifs de la connexion (pour les tests et le diagnostic)."""
    raw = engine.raw_connection()
    try:
        return _read_cipher_settings(raw.driver_connection)
    finally:
        raw.close()


def rekey(engine: sa.Engine, new_password: str) -> None:
    """Rechiffre la base ouverte avec `new_password` (SQLCipher `PRAGMA rekey`).

    Les connexions du pool gardent l'ancienne clé : l'appelant doit fermer ce moteur (`dispose`) et
    rouvrir la base avec le nouveau mot de passe.
    """
    _check_password(new_password)
    raw = engine.raw_connection()
    try:
        connection = raw.driver_connection
        if connection is None:
            raise RuntimeError("connexion indisponible")
        connection.execute(f"PRAGMA rekey = {_quote(new_password)}")
    finally:
        raw.close()
