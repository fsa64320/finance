"""Limitation des essais de connexion (FR-028).

Les 4 premiers échecs consécutifs ne ralentissent rien. À partir du 5ᵉ, le délai avant un nouvel
essai est de 15 secondes puis double à chaque échec, jusqu'à 15 minutes. Un succès remet le compteur
à zéro. L'état est en mémoire : un redémarrage le remet à zéro, mais verrouille aussi l'instance.
"""

import math
import threading
from collections.abc import Callable

FREE_ATTEMPTS = 5
BASE_DELAY = 15.0
MAX_DELAY = 900.0


class AttemptLimiter:
    def __init__(
        self,
        clock: Callable[[], float],
        *,
        free_attempts: int = FREE_ATTEMPTS,
        base_delay: float = BASE_DELAY,
        max_delay: float = MAX_DELAY,
    ) -> None:
        self._clock = clock
        self._free = free_attempts
        self._base = base_delay
        self._max = max_delay
        self._failures = 0
        self._blocked_until = 0.0
        self._lock = threading.Lock()

    @property
    def failures(self) -> int:
        return self._failures

    def retry_after(self) -> int:
        """Secondes à attendre avant le prochain essai (0 s'il est permis)."""
        with self._lock:
            remaining = self._blocked_until - self._clock()
            return math.ceil(remaining) if remaining > 0 else 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._free:
                exponent = min(self._failures - self._free, 30)
                delay = min(self._base * 2**exponent, self._max)
                self._blocked_until = self._clock() + delay

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._blocked_until = 0.0
