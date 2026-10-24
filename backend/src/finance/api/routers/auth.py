"""Routes d'authentification (contrat : tag `auth`)."""

from fastapi import APIRouter, Depends, Request, Response

from finance.api.deps import COOKIE_NAME, get_auth, require_session
from finance.api.schemas import AuthStatus, ChangePasswordRequest, PasswordRequest, UnlockRequest
from finance.auth.passwords import PasswordPolicyError
from finance.auth.service import AuthService
from finance.services.errors import ValidationFailed

router = APIRouter(prefix="/auth", tags=["auth"])


def _open_session(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/",
    )


@router.get("/status", response_model=AuthStatus)
def status(request: Request, auth: AuthService = Depends(get_auth)) -> AuthStatus:
    return AuthStatus(state=auth.state(request.cookies.get(COOKIE_NAME)))


@router.post(
    "/setup",
    status_code=204,
    response_class=Response,
    responses={
        409: {"description": "Mot de passe déjà créé"},
        422: {"description": "Mot de passe refusé"},
    },
)
def setup(
    body: PasswordRequest,
    request: Request,
    auth: AuthService = Depends(get_auth),
) -> Response:
    token = auth.setup(body.password)
    reply = Response(status_code=204)
    _open_session(request, reply, token)
    return reply


@router.post(
    "/unlock",
    status_code=204,
    response_class=Response,
    responses={
        401: {"description": "Mot de passe incorrect"},
        409: {"description": "Instance non initialisée"},
        422: {"description": "Données invalides"},
        429: {"description": "Trop d'essais"},
    },
)
def unlock(
    body: UnlockRequest,
    request: Request,
    auth: AuthService = Depends(get_auth),
) -> Response:
    token = auth.unlock(body.password)
    reply = Response(status_code=204)
    _open_session(request, reply, token)
    return reply


@router.post(
    "/lock",
    status_code=204,
    response_class=Response,
    responses={401: {"description": "Session absente ou expirée"}},
)
def lock(token: str = Depends(require_session), auth: AuthService = Depends(get_auth)) -> Response:
    auth.lock(token)
    reply = Response(status_code=204)
    reply.delete_cookie(COOKIE_NAME, path="/")
    return reply


@router.post(
    "/change-password",
    status_code=204,
    response_class=Response,
    responses={
        401: {"description": "Session absente ou mot de passe actuel incorrect"},
        422: {"description": "Nouveau mot de passe refusé"},
        429: {"description": "Trop d'essais"},
    },
)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    _: str = Depends(require_session),
    auth: AuthService = Depends(get_auth),
) -> Response:
    try:
        token = auth.change_password(body.current_password, body.new_password)
    except PasswordPolicyError as error:
        raise ValidationFailed.single("new_password", str(error)) from error
    reply = Response(status_code=204)
    _open_session(request, reply, token)
    return reply
