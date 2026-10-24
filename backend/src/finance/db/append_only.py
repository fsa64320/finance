"""Journal en ajout seul (principe II) : ni UPDATE ni DELETE sur les tables du journal.

Deux garde-fous :
- côté ORM, des écouteurs de session refusent la modification, la suppression et les requêtes
  UPDATE ou DELETE groupées avec un message clair (`AppendOnlyError`) ;
- côté base, des déclencheurs SQLite (créés par la migration initiale) refusent tout UPDATE et
  DELETE, même en SQL brut.

Une correction ajoute une ligne : voir `transaction_version`.
"""

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, UOWTransaction

PROTECTED_TABLES = (
    "transaction",
    "transaction_version",
    "transfer_group",
    "price",
    "declared_balance",
    "rate",
    "import_batch",
)


class AppendOnlyError(Exception):
    """Tentative de modifier ou de supprimer une ligne du journal."""


def _refuse(table: str, action: str) -> AppendOnlyError:
    return AppendOnlyError(f"la table {table} est en ajout seul : {action} interdit")


def _before_flush(session: Session, flush_context: UOWTransaction, instances: object) -> None:
    for obj in session.dirty:
        table = getattr(obj, "__tablename__", None)
        if table in PROTECTED_TABLES and session.is_modified(obj):
            raise _refuse(table, "modification")
    for obj in session.deleted:
        table = getattr(obj, "__tablename__", None)
        if table in PROTECTED_TABLES:
            raise _refuse(table, "suppression")


def _do_orm_execute(state: ORMExecuteState) -> None:
    if not (state.is_update or state.is_delete):
        return
    mapper = state.bind_mapper
    table = getattr(mapper.class_, "__tablename__", None) if mapper is not None else None
    if table in PROTECTED_TABLES:
        action = "modification" if state.is_update else "suppression"
        raise _refuse(str(table), action)


_installed = False


def install_guards() -> None:
    """Branche les écouteurs sur toutes les sessions ; sans effet si déjà fait."""
    global _installed
    if _installed:
        return
    event.listen(Session, "before_flush", _before_flush)
    event.listen(Session, "do_orm_execute", _do_orm_execute)
    _installed = True


def trigger_names(table: str) -> tuple[str, str]:
    return f"{table}_no_update", f"{table}_no_delete"
