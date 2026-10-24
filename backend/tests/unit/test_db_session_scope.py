"""Lecture de ses écritures : une réponse ne part qu'une fois la transaction validée.

Par défaut, FastAPI exécute la fin d'une dépendance à `yield` *après* l'envoi de la réponse. Le
client pouvait donc recevoir « 201 » puis relire des données encore non validées (tableau de bord
à 0 alors qu'un versement venait d'être enregistré). La session doit être validée avant l'envoi.
"""

from typing import Any

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from finance.api.deps import get_db_session
from finance.config import Settings
from finance.main import create_app


def session_dependencies(dependant: Dependant) -> list[Any]:
    found = []
    for dependency in dependant.dependencies:
        if dependency.call is get_db_session:
            found.append(dependency)
        found.extend(session_dependencies(dependency))
    return found


def test_every_route_commits_before_the_response_is_sent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    app = create_app(Settings(data_dir=tmp_path, host="127.0.0.1", port=8000))
    checked = 0
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for dependency in session_dependencies(route.dependant):
            checked += 1
            assert dependency.scope == "function", f"{route.methods} {route.path}"
    assert checked >= 30
