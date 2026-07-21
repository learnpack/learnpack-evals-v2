"""Ports shared by every module.

Ports are declared in the inner layers and implemented outside (ARCHITECTURE.md §2).
Nothing here may import a framework.
"""

from typing import Protocol, runtime_checkable

from app.shared.domain.events import DomainEvent


@runtime_checkable
class EventPublisherPort(Protocol):
    """Publishes domain events. The adapter decides how (MVP: outbox row, ADR-0003)."""

    def publish(self, event: DomainEvent) -> None: ...


@runtime_checkable
class UnitOfWorkPort(Protocol):
    """One transactional boundary per use case: aggregate(s) + events commit together."""

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
