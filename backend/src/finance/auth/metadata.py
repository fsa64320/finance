"""Petit fichier de métadonnées hors de la base chiffrée (data-model.md, Setting).

Il indique si l'instance est initialisée avant tout déverrouillage. Il ne contient aucun secret :
le sel de dérivation est dans l'en-tête du fichier SQLCipher lui-même.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FORMAT = 1
DATABASE_NAME = "finance.db"
METADATA_NAME = "instance.json"


def database_path(data_dir: Path) -> Path:
    return data_dir / DATABASE_NAME


def metadata_path(data_dir: Path) -> Path:
    return data_dir / METADATA_NAME


def is_initialized(data_dir: Path) -> bool:
    """Vrai dès qu'une base ou ses métadonnées existent : on n'écrase jamais une base."""
    return metadata_path(data_dir).exists() or database_path(data_dir).exists()


def ensure_data_dir(data_dir: Path) -> None:
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    data_dir.chmod(0o700)


def write_metadata(data_dir: Path, cipher: dict[str, Any]) -> None:
    ensure_data_dir(data_dir)
    content = {
        "format": FORMAT,
        "created_at": datetime.now(UTC).isoformat(),
        "cipher": cipher,
    }
    target = metadata_path(data_dir)
    temporary = target.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(content, handle, indent=2)
    os.replace(temporary, target)


def read_metadata(data_dir: Path) -> dict[str, Any] | None:
    path = metadata_path(data_dir)
    if not path.exists():
        return None
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded
