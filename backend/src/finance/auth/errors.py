"""Erreurs du service d'authentification, traduites en réponses HTTP par la couche API."""


class AuthError(Exception):
    """Racine des erreurs d'authentification."""


class AlreadyInitializedError(AuthError):
    """Le mot de passe est déjà créé : /auth/setup n'est plus possible."""


class NotInitializedError(AuthError):
    """Aucun mot de passe n'est encore créé."""


class DatabaseMissingError(AuthError):
    """L'instance est initialisée mais son fichier de base a disparu."""


class InvalidCredentialsError(AuthError):
    """Mot de passe incorrect."""


class TooManyAttemptsError(AuthError):
    """Trop d'échecs consécutifs : réessayer après `retry_after` secondes."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"réessayer dans {retry_after} secondes")
        self.retry_after = retry_after


class SessionRequiredError(AuthError):
    """Aucune session valide (absente, inconnue ou expirée)."""


class LockedError(AuthError):
    """L'instance est verrouillée : la base n'est pas ouverte."""
