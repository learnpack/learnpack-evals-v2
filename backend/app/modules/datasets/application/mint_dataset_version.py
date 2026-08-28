"""Use case: freeze the next membership as a version (ADR-0058 §1, §3, §4)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.datasets.application.ports import DatasetRepositoryPort
from app.modules.datasets.domain import events
from app.modules.datasets.domain.dataset import (
    Dataset,
    DatasetNotFound,
    DatasetVersion,
    canonical_members,
)
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


@dataclass(frozen=True)
class MintDatasetVersionCommand:
    dataset_id: UUID
    note: str
    members: list[UUID]
    created_by: UUID


class MintDatasetVersion:
    def __init__(
        self,
        datasets: DatasetRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._datasets = datasets
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: MintDatasetVersionCommand) -> tuple[Dataset, DatasetVersion]:
        dataset = self._datasets.get(command.dataset_id)
        if dataset is None:
            raise DatasetNotFound(f"dataset {command.dataset_id} is not declared")

        previous = dataset.latest_version
        # Read before minting: afterwards the aggregate's latest version IS the new one, and
        # the diff this event exists to carry would compare a set with itself.
        was = set(previous.members) if previous is not None else set()

        version = dataset.mint_version(
            version_id=new_id(),
            members=command.members,
            note=command.note,
            created_by=command.created_by,
            at=datetime.now(UTC),
        )

        now = set(version.members)
        self._datasets.append_version(dataset.id, version)
        self._publisher.publish(
            events.dataset_version_created(
                dataset,
                version,
                added=canonical_members(now - was),
                removed=canonical_members(was - now),
            )
        )
        self._uow.commit()
        return dataset, version
