"""Création de l'application FastAPI : API versionnée sous /api/v1 et frontend compilé."""

import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from finance.api.deps import COOKIE_NAME
from finance.api.errors import install_error_handlers
from finance.api.routers import accounts as accounts_router
from finance.api.routers import auth as auth_router
from finance.api.routers import dashboard as dashboard_router
from finance.api.routers import imports as imports_router
from finance.api.routers import instruments as instruments_router
from finance.api.routers import prices as prices_router
from finance.api.routers import settings as settings_router
from finance.api.routers import transactions as transactions_router
from finance.api.security import (
    MaxBodySizeMiddleware,
    OriginCheckMiddleware,
    SecurityHeadersMiddleware,
)
from finance.api.static import mount_frontend
from finance.auth.service import AuthService
from finance.config import Settings, load_settings
from finance.prices.base import Providers
from finance.prices.defaults import default_providers
from finance.services.imports import PreviewState, PreviewStore

__all__ = ["COOKIE_NAME", "create_app"]

API_PREFIX = "/api/v1"


def create_app(
    settings: Settings | None = None,
    *,
    clock: Callable[[], float] | None = None,
    providers: Providers | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    auth = AuthService(settings, clock=clock or time.monotonic)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        auth.shutdown()

    # Pas de /docs, /redoc ni /openapi.json : le contrat est dans le dépôt, et l'application ne
    # sert aucune page chargée depuis un CDN.
    app = FastAPI(
        title="Finance API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.auth = auth
    app.state.import_previews = PreviewStore[PreviewState]()
    app.state.providers = providers or default_providers()
    install_error_handlers(app)
    app.include_router(auth_router.router, prefix=API_PREFIX)
    app.include_router(accounts_router.router, prefix=API_PREFIX)
    app.include_router(instruments_router.router, prefix=API_PREFIX)
    app.include_router(transactions_router.router, prefix=API_PREFIX)
    app.include_router(dashboard_router.router, prefix=API_PREFIX)
    app.include_router(imports_router.router, prefix=API_PREFIX)
    app.include_router(prices_router.router, prefix=API_PREFIX)
    app.include_router(settings_router.router, prefix=API_PREFIX)

    frontend = static_dir or settings.static_dir
    if frontend is not None:
        mount_frontend(app, frontend)

    # Le dernier ajouté est le plus externe : les en-têtes de sécurité couvrent aussi les refus.
    app.add_middleware(MaxBodySizeMiddleware)
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(SecurityHeadersMiddleware)
    return app
