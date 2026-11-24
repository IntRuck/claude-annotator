"""Database engine and the per-request session (one transaction per request, like Spring's @Transactional)."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from annotator.config.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def open_session() -> Session:
    """A session outside a request (e.g. the live-update listener). Use it in a `with` block."""
    return _session_factory()()


def libpq_dsn() -> str:
    """DATABASE_URL in the plain form psycopg itself takes (no SQLAlchemy `+psycopg` driver part)."""
    return make_url(get_settings().database_url).set(drivername="postgresql").render_as_string(hide_password=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: commits when the request succeeds, rolls back on any error."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
