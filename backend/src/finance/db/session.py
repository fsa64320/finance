"""Fabrique de sessions : installe les garde-fous du journal en ajout seul."""

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from finance.db.append_only import install_guards


def make_session_factory(engine: sa.Engine) -> sessionmaker[Session]:
    install_guards()
    return sessionmaker(engine, expire_on_commit=False)
