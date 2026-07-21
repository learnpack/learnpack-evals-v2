"""Unit of work — closes the outbox cycle (ADR-0003).

The aggregate and its events are written through the same `Session`, so they commit
atomically. Policies run only afterwards, when the event is already durable: if one fails,
the event is still in `events` and can be replayed.
"""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.platform.db import SessionLocal
from app.platform.events import EventDispatcher, OutboxEventPublisher
from app.platform.events import dispatcher as default_dispatcher


class UnitOfWork:
    """One transactional boundary per use case (`UnitOfWorkPort`)."""

    def __init__(self, session: Session, dispatcher: EventDispatcher | None = None) -> None:
        self.session = session
        self.events = OutboxEventPublisher(session)
        self._dispatcher = dispatcher or default_dispatcher

    def commit(self) -> None:
        self.session.commit()
        # Only after the commit — see module docstring.
        self._dispatcher.dispatch(self.events.collect())

    def rollback(self) -> None:
        self.session.rollback()
        self.events.collect()  # drop events that never became durable


def get_uow() -> Iterator[UnitOfWork]:
    """FastAPI dependency: one unit of work per request."""
    session = SessionLocal()
    uow = UnitOfWork(session)
    try:
        yield uow
    except Exception:
        uow.rollback()
        raise
    finally:
        session.close()
