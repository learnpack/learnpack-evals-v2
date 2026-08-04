"""Use case: the human act that qualifies an adapter version (12-define, ADR-0012).

Accepting `(package_format, adapter_version)` is what lets the team discard "broken
extraction" as an alternative explanation — and what arms the auto-profiling policy.
Repeated per adapter version; idempotent per pair.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.content_profiling.application.ports import AcceptanceRepositoryPort
from app.modules.content_profiling.domain import events
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


@dataclass(frozen=True)
class AcceptExtractionCommand:
    package_format: str
    adapter_version: str
    accepted_by: UUID


class AcceptExtraction:
    def __init__(
        self,
        acceptances: AcceptanceRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._acceptances = acceptances
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: AcceptExtractionCommand) -> bool:
        """True when the acceptance was newly recorded; replays never re-emit."""
        newly_accepted = self._acceptances.accept(
            command.package_format, command.adapter_version, command.accepted_by
        )
        if newly_accepted:
            self._publisher.publish(
                events.extraction_accepted(
                    command.package_format, command.adapter_version, command.accepted_by
                )
            )
        self._uow.commit()
        return newly_accepted
