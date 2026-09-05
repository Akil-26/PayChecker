"""Database engine and session management — production grade.

Supports both SQLite (development) and PostgreSQL (production) via DATABASE_URL.
Connection pooling is configured for PostgreSQL; SQLite uses a single thread-safe
connection.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _engine_kwargs(database_url: str, settings) -> dict:
    kwargs: dict = {"echo": settings.db_echo, "future": True}

    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL — production connection pool
        kwargs.update({
            "pool_pre_ping": True,
            "pool_size":     settings.db_pool_size,
            "max_overflow":  settings.db_max_overflow,
            "pool_timeout":  settings.db_pool_timeout,
            "pool_recycle":  1800,  # recycle connections every 30 minutes
        })

    return kwargs


@lru_cache
def get_engine() -> Engine:
    """Return the cached SQLAlchemy engine."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        **_engine_kwargs(settings.database_url, settings),
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the cached session factory."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def ping_db() -> bool:
    """Check the database is reachable. Used by the health endpoint."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_engine_cache() -> None:
    """Dispose the engine and clear caches. Used between tests."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session scope for scripts and background tasks."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
