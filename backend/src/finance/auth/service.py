"""Service d'authentification : le mot de passe est la clé de la base chiffrée (FR-028).

États :
- `uninitialized` : aucun mot de passe créé ;
- `locked` : la base est fermée (démarrage, `lock`, expiration de la dernière session) ;
- `unlocked` : la base est ouverte et la session présentée est valide.

Un seul processus garde la base ouverte en mémoire (research.md §2). Aucune récupération n'existe
en cas d'oubli du mot de passe.
"""

import threading
import time
from collections.abc import Callable
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from finance.auth import metadata
from finance.auth.errors import (
    AlreadyInitializedError,
    DatabaseMissingError,
    InvalidCredentialsError,
    LockedError,
    NotInitializedError,
    TooManyAttemptsError,
)
from finance.auth.passwords import validate_password
from finance.auth.ratelimit import AttemptLimiter
from finance.auth.sessions import SessionStore
from finance.config import Settings
from finance.db.engine import (
    DatabaseExistsError,
    DatabaseNotFoundError,
    WrongPasswordError,
    cipher_settings,
    open_database,
)
from finance.db.migrate import upgrade
from finance.db.session import make_session_factory

State = Literal["uninitialized", "locked", "unlocked"]


class AuthService:
    def __init__(self, settings: Settings, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._data_dir = settings.data_dir
        self._limiter = AttemptLimiter(clock)
        self._sessions = SessionStore(clock)
        self._engine: sa.Engine | None = None
        self._factory: sessionmaker[Session] | None = None
        self._lock = threading.RLock()

    @property
    def is_open(self) -> bool:
        return self._engine is not None

    def _close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
        self._engine = None
        self._factory = None

    def validate(self, token: str | None) -> bool:
        """Vrai si `token` désigne une session valide ; verrouille quand plus aucune ne reste."""
        with self._lock:
            valid = self._sessions.validate(token)
            if not self._sessions.has_active():
                self._close()
            return valid and self._engine is not None

    def state(self, token: str | None) -> State:
        with self._lock:
            if not metadata.is_initialized(self._data_dir):
                return "uninitialized"
            return "unlocked" if self.validate(token) else "locked"

    def setup(self, password: str) -> str:
        """Crée la base chiffrée et le mot de passe ; renvoie le jeton de la première session."""
        validate_password(password)
        with self._lock:
            if metadata.is_initialized(self._data_dir):
                raise AlreadyInitializedError("le mot de passe est déjà créé")
            metadata.ensure_data_dir(self._data_dir)
            database = metadata.database_path(self._data_dir)
            try:
                engine = open_database(database, password, create=True)
            except DatabaseExistsError as error:
                raise AlreadyInitializedError("une base existe déjà") from error
            try:
                database.chmod(0o600)
                upgrade(engine)
                metadata.write_metadata(self._data_dir, cipher_settings(engine))
            except BaseException:
                engine.dispose()
                database.unlink(missing_ok=True)
                metadata.metadata_path(self._data_dir).unlink(missing_ok=True)
                raise
            self._engine = engine
            self._limiter.record_success()
            return self._sessions.create()

    def unlock(self, password: str) -> str:
        """Ouvre la base avec `password` ; renvoie le jeton d'une nouvelle session."""
        with self._lock:
            if not metadata.is_initialized(self._data_dir):
                raise NotInitializedError("aucun mot de passe n'est créé")
            delay = self._limiter.retry_after()
            if delay > 0:
                raise TooManyAttemptsError(delay)
            try:
                engine = open_database(metadata.database_path(self._data_dir), password)
            except DatabaseNotFoundError as error:
                raise DatabaseMissingError("le fichier de base a disparu") from error
            except (WrongPasswordError, ValueError) as error:
                self._limiter.record_failure()
                raise InvalidCredentialsError("mot de passe incorrect") from error
            self._limiter.record_success()
            if self._engine is None:
                try:
                    upgrade(engine)
                except BaseException:
                    engine.dispose()
                    raise
                self._engine = engine
            else:
                engine.dispose()  # simple vérification du mot de passe : la base est déjà ouverte
            return self._sessions.create()

    def lock(self, token: str | None = None) -> None:
        """Ferme toutes les sessions et la base."""
        with self._lock:
            self._sessions.revoke(token)
            self._sessions.clear()
            self._close()

    def engine(self) -> sa.Engine:
        with self._lock:
            if self._engine is None:
                raise LockedError("l'instance est verrouillée")
            return self._engine

    def session_factory(self) -> sessionmaker[Session]:
        with self._lock:
            if self._factory is None:
                self._factory = make_session_factory(self.engine())
            return self._factory

    def shutdown(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._close()
