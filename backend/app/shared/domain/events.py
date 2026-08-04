"""Base domain event — pure Python, no framework imports (ARCHITECTURE.md §1).

A domain event is a past fact. State evolves by publishing them; policies react
(events-first, ARCHITECTURE.md §4). In the MVP, publishing one is realised as an INSERT
into the `events` table inside the aggregate's transaction (outbox, ADR-0003).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """A past fact about an aggregate.

    `event_type` uses the ubiquitous language verbatim (GLOSSARY.md): `ContentVersionRegistered`,
    `EvaluationSubmitted`, `ContentEvaluationCompleted`, ...
    """

    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
