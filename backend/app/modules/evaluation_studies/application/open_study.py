"""Use case: open the study — the dataset is fixed from here on (12-define invariant 2)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.evaluation_studies.application.ports import StudyRepositoryPort
from app.modules.evaluation_studies.domain import events
from app.modules.evaluation_studies.domain.model import Study, StudyNotFound
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


@dataclass(frozen=True)
class OpenStudyCommand:
    study_id: UUID


class OpenStudy:
    def __init__(
        self,
        studies: StudyRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: OpenStudyCommand) -> Study:
        study = self._studies.get_by_id(command.study_id)
        if study is None:
            raise StudyNotFound(f"study {command.study_id} is not declared")

        study.open(datetime.now(UTC))
        self._studies.update(study)
        self._publisher.publish(events.study_opened(study))
        self._uow.commit()
        return study
