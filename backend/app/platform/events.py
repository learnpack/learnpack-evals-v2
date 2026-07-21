"""Events-first over Postgres: outbox + in-process dispatcher (ADR-0003).

Publishing an event is an INSERT into `events` using the *use case's own session*, so it
commits atomically with the aggregate. After the commit, the dispatcher hands the event to
the subscribed policies (synchronous in the MVP).

Replacing this dispatcher with a real bus / integration-event relay later does not change
any module contract (ARCHITECTURE.md §4).
"""

import json
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.shared.domain.events import DomainEvent

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent], None]


class OutboxEventPublisher:
    """`EventPublisherPort` adapter — appends the event to the `events` table.

    Collects the published events so the caller can dispatch them *after* the commit.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._pending: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO events (occurred_at, event_type, aggregate_type, aggregate_id, payload)
                VALUES (:occurred_at, :event_type, :aggregate_type, :aggregate_id, :payload)
                """
            ),
            {
                "occurred_at": event.occurred_at,
                "event_type": event.event_type,
                "aggregate_type": event.aggregate_type,
                "aggregate_id": event.aggregate_id,
                "payload": json.dumps(event.payload),
            },
        )
        self._pending.append(event)

    def collect(self) -> list[DomainEvent]:
        """Drain the events published so far (call after commit, before dispatching)."""
        events, self._pending = self._pending, []
        return events


class EventDispatcher:
    """Routes committed events to the policies that subscribed to them.

    Handlers must be idempotent (`event_type + aggregate_id`), so a failed run can be
    reprocessed from the `events` table — ADR-0003.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def dispatch(self, events: list[DomainEvent]) -> None:
        """Deliver events to their subscribers. Call *after* the transaction committed."""
        for event in events:
            for handler in self._handlers[event.event_type]:
                try:
                    handler(event)
                except Exception:
                    # The event is durably stored, so a failed policy can be replayed.
                    logger.exception(
                        "policy failed for %s(%s)", event.event_type, event.aggregate_id
                    )

    def subscriptions(self) -> dict[str, list[Any]]:
        return dict(self._handlers)


# Application-wide dispatcher. Policies register on it at wiring time (main.py).
# Block 1 leaves it empty; orchestration's quorum policy subscribes in block 3.
dispatcher = EventDispatcher()
