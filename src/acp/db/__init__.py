"""Database plumbing: engine, session factory, startup init."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from acp.db.models import Base

_engines: dict[str, object] = {}
_SessionFactory: dict[str, sessionmaker] = {}


def get_engine(database_url: str):
    if database_url not in _engines:
        kwargs = {}
        if database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engines[database_url] = create_engine(database_url, pool_pre_ping=True, **kwargs)
    return _engines[database_url]


def get_session_factory(database_url: str):
    if database_url not in _SessionFactory:
        _SessionFactory[database_url] = sessionmaker(
            bind=get_engine(database_url), autoflush=False, expire_on_commit=False)
    return _SessionFactory[database_url]


def init_db(database_url: str) -> None:
    """Dev startup: create tables (production should use Alembic)."""
    Base.metadata.create_all(get_engine(database_url))


def reset_db_cache() -> None:
    """Test helper: drop cached engines/session factories so fresh DB URLs can be used."""
    _engines.clear()
    _SessionFactory.clear()
