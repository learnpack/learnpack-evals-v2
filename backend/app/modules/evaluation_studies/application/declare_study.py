"""Use case: declare a study — the round, named (13-code §3.6, ADR-0043 §7)."""

from dataclasses import dataclass

from app.modules.evaluation_studies.application.ports import StudyRepositoryPort
from app.modules.evaluation_studies.domain import events
from app.modules.evaluation_studies.domain.model import Study
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


@dataclass(frozen=True)
class DeclareStudyCommand:
    name: str
    description: str | None = None


class DeclareStudy:
    def __init__(
        self,
        studies: StudyRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: DeclareStudyCommand) -> Study:
        study = Study(id=new_id(), name=command.name, description=command.description)
        self._studies.add(study)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.study_declared(study))
        self._uow.commit()
        return study
