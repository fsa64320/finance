"""Format d'erreur commun {code, message, details} et traduction des erreurs du domaine."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from finance.auth.errors import (
    AlreadyInitializedError,
    DatabaseMissingError,
    InvalidCredentialsError,
    LockedError,
    NotInitializedError,
    SessionRequiredError,
    TooManyAttemptsError,
)
from finance.auth.passwords import PasswordPolicyError

logger = logging.getLogger("finance.api")


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(body, status_code=status_code, headers=headers)


def _validation_message(error: dict[str, Any]) -> str:
    kind = error.get("type", "")
    context = error.get("ctx", {})
    if kind == "string_too_short":
        return f"doit faire au moins {context.get('min_length')} caractères"
    if kind == "string_too_long":
        return f"doit faire au plus {context.get('max_length')} caractères"
    if kind == "missing":
        return "champ obligatoire"
    return "valeur invalide"


async def _validation_handler(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error
    details = [
        {"field": str(item["loc"][-1]), "message": _validation_message(item)}
        for item in error.errors()
        if item["loc"]
    ]
    return error_response(422, "validation_error", "Données invalides", details=details)


async def _http_handler(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, StarletteHTTPException):
        raise error
    code = {404: "not_found", 405: "method_not_allowed"}.get(error.status_code, "http_error")
    headers = dict(error.headers) if error.headers else None
    return error_response(error.status_code, code, str(error.detail), headers=headers)


async def _weak_password_handler(_: Request, error: Exception) -> JSONResponse:
    return error_response(
        422,
        "weak_password",
        "Mot de passe refusé",
        details=[{"field": "password", "message": str(error)}],
    )


def _simple(status_code: int, code: str, message: str) -> Any:
    async def handler(_: Request, __: Exception) -> JSONResponse:
        return error_response(status_code, code, message)

    return handler


async def _too_many_handler(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, TooManyAttemptsError):
        raise error
    return error_response(
        429,
        "too_many_attempts",
        f"Trop d'essais : réessayez dans {error.retry_after} secondes.",
        headers={"Retry-After": str(error.retry_after)},
    )


async def _unexpected_handler(_: Request, error: Exception) -> JSONResponse:
    logger.error("erreur inattendue : %s", type(error).__name__)  # jamais le contenu de la requête
    return error_response(500, "internal_error", "Erreur interne")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(PasswordPolicyError, _weak_password_handler)
    app.add_exception_handler(TooManyAttemptsError, _too_many_handler)
    app.add_exception_handler(
        AlreadyInitializedError,
        _simple(409, "already_initialized", "Le mot de passe est déjà créé."),
    )
    app.add_exception_handler(
        NotInitializedError,
        _simple(409, "not_initialized", "Aucun mot de passe n'est encore créé."),
    )
    app.add_exception_handler(
        DatabaseMissingError,
        _simple(409, "database_missing", "Le fichier de données est introuvable."),
    )
    app.add_exception_handler(
        InvalidCredentialsError,
        _simple(401, "invalid_credentials", "Mot de passe incorrect."),
    )
    app.add_exception_handler(
        SessionRequiredError,
        _simple(401, "session_required", "Session absente ou expirée."),
    )
    app.add_exception_handler(LockedError, _simple(423, "locked", "L'instance est verrouillée."))
    app.add_exception_handler(Exception, _unexpected_handler)
