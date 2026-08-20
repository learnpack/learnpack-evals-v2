"""SQLAlchemy engine and session (frameworks & drivers layer).

Synchronous sessions on purpose: they are simpler and the MVP's workload needs no async
concurrency. Async would *not* break the outbox's atomicity — sync is just preferable here.
Revisable if concurrency grows (08-code.md §3).
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Built lazily so importing this module never requires a configured database."""
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set (see backend/.env.example)")
    # `pool_pre_ping` matters on Neon: it scales to zero and resumes on demand (ADR-0003),
    # so a pooled connection can be stale. The pool's size is declared rather than inherited
    # because it bounds how many courses a batch may evaluate at once (`config.py`).
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        future=True,
    )


def SessionLocal() -> Session:  # noqa: N802 — reads as a sessionmaker at call sites
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one transaction per request."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
