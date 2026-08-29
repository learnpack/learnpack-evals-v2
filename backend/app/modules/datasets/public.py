"""Public surface of Datasets (ARCHITECTURE.md §3).

The **only** module in this package other modules may import. What it publishes is the answer
to one question — *which courses are in this version* — because that is what a round needs in
order to be opened against a set somebody named (ADR-0058 §5).
"""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.datasets.infrastructure.repository import SqlAlchemyDatasetRepository
from app.platform.uow import UnitOfWork, get_uow

# Events this module publishes — the contract subscribers rely on.
DATASET_DECLARED = "DatasetDeclared"
DATASET_VERSION_CREATED = "DatasetVersionCreated"
DATASET_RENAMED = "DatasetRenamed"

__all__ = [
    "DATASET_DECLARED",
    "DATASET_RENAMED",
    "DATASET_VERSION_CREATED",
    "DatasetVersionDTO",
    "DatasetsQueries",
    "get_datasets_queries",
]


@dataclass(frozen=True)
class DatasetVersionDTO:
    """A frozen membership, named well enough to be read on a screen.

    The dataset's name rides along because every consumer that resolves a version also wants
    to say which set it belongs to, and a second query for one string is a join nobody needs.
    """

    version_id: UUID
    dataset_id: UUID
    dataset_name: str
    ordinal: int
    note: str
    content_ids: tuple[UUID, ...]


class DatasetsQueries:
    """Read-only contract of Datasets."""

    def __init__(self, session: Session) -> None:
        self._datasets = SqlAlchemyDatasetRepository(session)

    def get_version(self, version_id: UUID) -> DatasetVersionDTO | None:
        dataset = self._datasets.find_dataset_of_version(version_id)
        if dataset is None:
            return None
        version = dataset.version(version_id)
        if version is None:  # pragma: no cover — the lookup resolved it a moment ago
            return None
        return DatasetVersionDTO(
            version_id=version.id,
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            ordinal=version.ordinal,
            note=version.note,
            content_ids=version.members,
        )


def get_datasets_queries(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> DatasetsQueries:
    return DatasetsQueries(uow.session)
