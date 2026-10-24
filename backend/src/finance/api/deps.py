"""Dépendances FastAPI : service d'authentification, session exigée, session de base de données."""

from collections.abc import Iterator

from fastapi import Depends, Request
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from finance.auth.errors import SessionRequiredError
from finance.auth.service import AuthService

COOKIE_NAME = "finance_session"

session_cookie = APIKeyCookie(name=COOKIE_NAME, scheme_name="sessionCookie", auto_error=False)


def get_auth(request: Request) -> AuthService:
    auth: AuthService = request.app.state.auth
    return auth


def require_session(
    token: str | None = Depends(session_cookie), auth: AuthService = Depends(get_auth)
) -> str:
    """Exige une session valide ; renvoie son jeton."""
    if token is None or not auth.validate(token):
        raise SessionRequiredError("session absente ou expirée")
    return token


def get_db_session(
    _: str = Depends(require_session), auth: AuthService = Depends(get_auth)
) -> Iterator[Session]:
    """Session SQLAlchemy sur la base déverrouillée : validée si la route réussit, sinon annulée."""
    with auth.session_factory()() as session:
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
