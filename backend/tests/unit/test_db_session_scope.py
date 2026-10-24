"""Lecture de ses écritures : une réponse ne part qu'une fois la transaction validée.

Par défaut, FastAPI exécute la fin d'une dépendance à `yield` *après* l'envoi de la réponse. Le
client pouvait donc recevoir « 201 » puis relire des données encore non validées (tableau de bord
à 0 alors qu'un versement venait d'être enregistré). La session doit être validée avant l'envoi.
"""

import importlib
import pkgutil
from typing import Any

from fastapi import APIRouter
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

import finance.api.routers as routers_package
from finance.api.deps import get_db_session


def session_dependencies(dependant: Dependant) -> list[Any]:
    found = []
    for dependency in dependant.dependencies:
        if dependency.call is get_db_session:
            found.append(dependency)
        found.extend(session_dependencies(dependency))
    return found


def test_every_route_commits_before_the_response_is_sent() -> None:
    checked = 0
    for module_info in pkgutil.iter_modules(routers_package.__path__):
        module = importlib.import_module(f"finance.api.routers.{module_info.name}")
        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            continue
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            for dependency in session_dependencies(route.dependant):
                checked += 1
                assert dependency.scope == "function", f"{route.methods} {route.path}"
    assert checked >= 30
