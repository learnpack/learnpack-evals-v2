"""Use case: pin the instrument version — ONCE, before opening (12-define invariant 1).

The pin starts the reproducibility commitment: the study reports against this exact norm
forever. Only a published version is pinnable — a draft is still someone else's to edit.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation_studies.application.ports import (
    DesignGatewayPort,
    StudyRepositoryPort,
)
from app.modules.evaluation_studies.domain import events
from app.modules.evaluation_studies.domain.model import Study, StudyNotFound
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class UnknownInstrument(Exception):
    """No instrument version with that id."""


class InstrumentNotPublished(Exception):
    """Only a published version is pinnable — a study never pins a draft."""


@dataclass(frozen=True)
class PinInstrumentCommand:
    study_id: UUID
    instrument_version_id: str


class PinInstrument:
    def __init__(
        self,
        studies: StudyRepositoryPort,
        instruments: DesignGatewayPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._instruments = instruments
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: PinInstrumentCommand) -> Study:
        study = self._studies.get_by_id(command.study_id)
        if study is None:
            raise StudyNotFound(f"study {command.study_id} is not declared")

        instrument = self._instruments.get_instrument(command.instrument_version_id)
        if instrument is None:
            raise UnknownInstrument(
                f"instrument version {command.instrument_version_id} does not exist"
            )
        if not instrument.is_published:
            raise InstrumentNotPublished(
                f"instrument version {command.instrument_version_id} is {instrument.status}; "
                "publish it before pinning"
            )

        study.pin_instrument(command.instrument_version_id)
        self._studies.update(study)
        self._publisher.publish(events.instrument_pinned(study))
        self._uow.commit()
        return study
