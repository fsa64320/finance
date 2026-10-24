"""Environnement Alembic.

Deux modes :
- appel par le code (`finance.db.migrate.upgrade`) : la connexion chiffrée déjà ouverte est passée
  par `config.attributes["connection"]` ;
- ligne de commande de développement : `alembic -x db=chemin/vers/dev.db revision --autogenerate`.
  Ce mode ouvre une base de développement **non chiffrée** : ne jamais l'utiliser avec de vraies
  données.
"""

from alembic import context
from sqlalchemy import create_engine
from sqlcipher3 import dbapi2 as sqlcipher

from finance.db.models import Base

config = context.config
target_metadata = Base.metadata


def run_with(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite ne sait pas tout modifier en place : les migrations futures passent par le mode batch.
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        run_with(connection)
        return
    path = context.get_x_argument(as_dictionary=True).get("db")
    if path is None:
        raise RuntimeError("passer la base de développement : alembic -x db=chemin/vers/dev.db ...")
    engine = create_engine(
        "sqlite://",
        module=sqlcipher,
        creator=lambda: sqlcipher.connect(path),
    )
    with engine.connect() as connection:
        run_with(connection)
        connection.commit()


if context.is_offline_mode():
    raise RuntimeError("le mode hors ligne n'est pas pris en charge")
run_migrations_online()
