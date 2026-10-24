"""Point d'entrée : `python -m finance` démarre le serveur (un seul processus uvicorn).

Le conteneur n'a qu'un processus car la base chiffrée et les sessions vivent en mémoire de ce
processus (research.md §2).
"""

import uvicorn

from finance.config import load_settings
from finance.main import create_app


def main() -> None:
    settings = load_settings()
    # Pas de journal d'accès : les adresses contiennent des identifiants de comptes et d'actifs.
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, access_log=False)


if __name__ == "__main__":
    main()
