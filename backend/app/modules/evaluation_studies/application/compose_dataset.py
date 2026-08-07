"""Use case: compose the dataset — briefIds → contentIds from what is registered.

The recipe (briefIds) selects contents through the registry gateway; the resolved
contentIds are the materialized dataset, replaceable until `open` fixes it. Publishes no
event (13-code §5).
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluation_studies.application.ports import (
    RegistryGatewayPort,
    StudyRepositoryPort,
)
from app.modules.evaluation_studies.domain.model import Study, StudyNotFound
from app.shared.application.ports import UnitOfWorkPort


class UnknownBrief(Exception):
    """A brief in the recipe is not registered."""


@dataclass(frozen=True)
class ComposeDatasetCommand:
    study_id: UUID
    brief_ids: list[UUID]


class ComposeDataset:
    def __init__(
        self,
        studies: StudyRepositoryPort,
        registry: RegistryGatewayPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._studies = studies
        self._registry = registry
        self._uow = uow

    def __call__(self, command: ComposeDatasetCommand) -> Study:
        study = self._studies.get_by_id(command.study_id)
        if study is None:
            raise StudyNotFound(f"study {command.study_id} is not declared")

        for brief_id in command.brief_ids:
            if self._registry.get_brief(brief_id) is None:
                raise UnknownBrief(f"brief {brief_id} is not registered")

        contents = self._registry.get_contents_by_briefs(command.brief_ids)
        study.compose_dataset(
            brief_ids=tuple(command.brief_ids),
            content_ids=tuple(c.content_id for c in contents),
        )
        self._studies.update(study)
        self._uow.commit()
        return study
