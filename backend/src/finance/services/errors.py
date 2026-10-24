"""Erreurs métier des services, traduites en 404, 409 et 422 par la couche API."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldError:
    field: str
    message: str


class ServiceError(Exception):
    """Racine des erreurs métier."""


class NotFoundError(ServiceError):
    def __init__(self, kind: str, identifier: str) -> None:
        super().__init__(f"{kind} introuvable")
        self.kind = kind
        self.identifier = identifier


class ConflictError(ServiceError):
    """L'état actuel interdit l'opération (nom ou ISIN déjà pris)."""


class ValidationFailed(ServiceError):
    def __init__(self, details: list[FieldError]) -> None:
        super().__init__("; ".join(f"{d.field} : {d.message}" for d in details))
        self.details = details

    @classmethod
    def single(cls, field: str, message: str) -> "ValidationFailed":
        return cls([FieldError(field, message)])
