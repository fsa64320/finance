"""Sessions en mémoire (FR-028) : 30 minutes d'inactivité, 12 heures au plus.

Seule l'empreinte du jeton est conservée : un vidage mémoire ne livre pas de jeton utilisable.
"""

import hashlib
import secrets
import threading
from collections.abc import Callable

IDLE_TIMEOUT = 30 * 60.0
MAX_AGE = 12 * 3600.0


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class SessionStore:
    def __init__(
        self,
        clock: Callable[[], float],
        *,
        idle_timeout: float = IDLE_TIMEOUT,
        max_age: float = MAX_AGE,
    ) -> None:
        self._clock = clock
        self._idle = idle_timeout
        self._max_age = max_age
        self._sessions: dict[
            str, tuple[float, float]
        ] = {}  # empreinte -> (créée, dernière activité)
        self._lock = threading.Lock()

    def _expired(self, created: float, last_seen: float, now: float) -> bool:
        return now - last_seen > self._idle or now - created > self._max_age

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        now = self._clock()
        with self._lock:
            self._sessions[_digest(token)] = (now, now)
        return token

    def validate(self, token: str | None) -> bool:
        """Vrai si la session est valide ; une session valide voit son inactivité remise à zéro."""
        if not token:
            return False
        key = _digest(token)
        now = self._clock()
        with self._lock:
            entry = self._sessions.get(key)
            if entry is None:
                return False
            created, last_seen = entry
            if self._expired(created, last_seen, now):
                del self._sessions[key]
                return False
            self._sessions[key] = (created, now)
            return True

    def has_active(self) -> bool:
        now = self._clock()
        with self._lock:
            for key, (created, last_seen) in list(self._sessions.items()):
                if self._expired(created, last_seen, now):
                    del self._sessions[key]
            return bool(self._sessions)

    def revoke(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(_digest(token), None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
