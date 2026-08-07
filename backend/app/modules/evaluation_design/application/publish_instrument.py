"""Use case: publish an instrument version — the atomic, human act (design 12 inv. 4).

Validates the full evidential argument through the aggregate and emits
`InstrumentVersionPublished` carrying the complete snapshot (11-connect).
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation_design.application.ports import (
    DataRequirementRepositoryPort,
    InstrumentRepositoryPort,
    ReferenceDataPort,
)
from app.modules.evaluation_design.domain import events
from app.modules.evaluation_design.domain.instrument import InstrumentVersion
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class InstrumentNotFound(Exception):
    """No instrument version with that id exists."""


@dataclass(frozen=True)
class PublishInstrumentCommand:
    instrument_version_id: str
    published_by: UUID


class PublishInstrument:
    def __init__(
        self,
        instruments: InstrumentRepositoryPort,
        data_requirements: DataRequirementRepositoryPort,
        reference: ReferenceDataPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._instruments = instruments
        self._data_requirements = data_requirements
        self._reference = reference
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: PublishInstrumentCommand) -> InstrumentVersion:
        instrument = self._instruments.get(command.instrument_version_id)
        if instrument is None:
            raise InstrumentNotFound(
                f"instrument version {command.instrument_version_id} not found"
            )

        instrument.publish(
            published_by=command.published_by,
            known_data_requirements=set(self._data_requirements.get_all()),
            quality_dimensions=self._reference.quality_dimensions(),
            known_frameworks=self._reference.framework_ids(),
        )

        self._instruments.set_published(instrument)
        # Aggregate + event in the same transaction (ADR-0003); payload = full snapshot.
        self._publisher.publish(events.instrument_version_published(instrument))
        self._uow.commit()
        return instrument
