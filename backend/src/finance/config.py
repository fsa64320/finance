"""Configuration de l'application, lue dans l'environnement.

Aucun secret ici : le mot de passe de l'utilisateur ne vit jamais dans l'environnement.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Constitution v1.1.0, principe I : la récupération automatique des prix reste désactivée
# tant que l'utilisateur ne l'a pas activée par un choix explicite (réglage en base).
PRICE_FETCH_DEFAULT = False

DEFAULT_DATA_DIR = "/data"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str
    port: int
    # Origines supplémentaires autorisées pour les requêtes qui modifient des données
    # (utile derrière un proxy inverse dont le nom d'hôte diffère).
    allowed_origins: tuple[str, ...] = ()
    # Dossier du frontend compilé servi par le backend ; None en développement (serveur Vite).
    static_dir: Path | None = None


def _read_port(raw: str | None) -> int:
    if raw is None:
        return DEFAULT_PORT
    try:
        port = int(raw)
    except ValueError as error:
        raise ValueError(f"FINANCE_PORT doit être un entier, reçu {raw!r}") from error
    if not 1 <= port <= 65535:
        raise ValueError(f"FINANCE_PORT doit être compris entre 1 et 65535, reçu {port}")
    return port


def _read_origins(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())


def load_settings() -> Settings:
    static = os.environ.get("FINANCE_STATIC_DIR")
    return Settings(
        data_dir=Path(os.environ.get("FINANCE_DATA_DIR", DEFAULT_DATA_DIR)),
        host=os.environ.get("FINANCE_HOST", DEFAULT_HOST),
        port=_read_port(os.environ.get("FINANCE_PORT")),
        allowed_origins=_read_origins(os.environ.get("FINANCE_ALLOWED_ORIGINS")),
        static_dir=Path(static) if static else None,
    )
