"""Intergiciels de sécurité (T033) : en-têtes, contrôle de l'origine, taille maximale des corps.

Écrits en ASGI pur pour ne pas dépendre du comportement de BaseHTTPMiddleware avec les flux.
"""

from collections.abc import Awaitable, Callable, Iterable, MutableMapping
from typing import Any

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
DEFAULT_BODY_LIMIT = 1024 * 1024
BODY_LIMITS = {
    "/api/v1/imports/preview": 10 * 1024 * 1024,
    "/api/v1/imports/commit": 10 * 1024 * 1024,
    "/api/v1/data/restore": 100 * 1024 * 1024,
}

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)

STATIC_HEADERS = {
    "content-security-policy": CONTENT_SECURITY_POLICY,
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "permissions-policy": "geolocation=(), camera=(), microphone=()",
}


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status_code)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope["path"].startswith("/api")
        is_https = scope.get("scheme") == "https"

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(message)
                for name, value in STATIC_HEADERS.items():
                    headers.setdefault(name, value)
                if is_api:
                    headers.setdefault("cache-control", "no-store")
                if is_https:
                    headers.setdefault("strict-transport-security", "max-age=31536000")
            await send(message)

        await self.app(scope, receive, send_with_headers)


class MutableHeaders:
    """Accès simple en écriture aux en-têtes d'un message `http.response.start`."""

    def __init__(self, message: MutableMapping[str, Any]) -> None:
        self._message = message
        self._raw: list[tuple[bytes, bytes]] = list(message.get("headers", []))
        message["headers"] = self._raw

    def setdefault(self, name: str, value: str) -> None:
        key = name.lower().encode("latin-1")
        if not any(existing == key for existing, _ in self._raw):
            self._raw.append((key, value.encode("latin-1")))


class OriginCheckMiddleware:
    """Refuse une requête qui modifie des données si son en-tête Origin vient d'un autre site.

    Sans en-tête Origin (curl, scripts), la requête passe : le cookie SameSite=Strict protège déjà
    les navigateurs, et ce contrôle ajoute une seconde barrière.
    """

    def __init__(self, app: ASGIApp, allowed_origins: Iterable[str] = ()) -> None:
        self.app = app
        self.allowed = {origin.rstrip("/") for origin in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in UNSAFE_METHODS:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if origin is not None:
                own = f"{scope.get('scheme', 'http')}://{headers.get('host', '')}"
                if origin != own and origin.rstrip("/") not in self.allowed:
                    response = _error(403, "forbidden_origin", "Origine de la requête refusée.")
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


class _TooLargeError(Exception):
    pass


class MaxBodySizeMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        default_limit: int = DEFAULT_BODY_LIMIT,
        limits: dict[str, int] | None = None,
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.limits = BODY_LIMITS if limits is None else limits

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return
        limit = self.limits.get(scope["path"], self.default_limit)
        declared = Headers(scope=scope).get("content-length")
        too_large = _error(413, "payload_too_large", "Le corps de la requête est trop volumineux.")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await too_large(scope, receive, send)
            return

        received = 0
        started = False

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLargeError
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted_receive, tracking_send)
        except _TooLargeError:
            if not started:
                await too_large(scope, receive, send)


Middleware = Callable[[ASGIApp], Awaitable[None]]
