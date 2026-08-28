"""Use case: declare a dataset — the concept and its first version, in one act (ADR-0058 §1).

One act and not two, because a dataset with no version is not a set: there would be nothing to
open a campaign against, and the intermediate state exists only to be left behind.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.datasets.application.ports import DatasetRepositoryPort
from app.modules.datasets.domain import events
from app.modules.datasets.domain.dataset import Dataset
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


@dataclass(frozen=True)
class DeclareDatasetCommand:
    name: str
    note: str
    members: list[UUID]
    declared_by: UUID
    description: str | None = None


class DeclareDataset:
    def __init__(
        self,
        datasets: DatasetRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._datasets = datasets
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: DeclareDatasetCommand) -> Dataset:
        now = datetime.now(UTC)
        dataset = Dataset(
            id=new_id(),
            name=command.name,
            description=command.description,
            created_by=command.declared_by,
            created_at=now,
        )
        version = dataset.mint_version(
            version_id=new_id(),
            members=command.members,
            note=command.note,
            created_by=command.declared_by,
            at=now,
        )

        self._datasets.add(dataset)
        self._publisher.publish(events.dataset_declared(dataset))
        # Both events, because both facts happened: something was named, and a membership was
        # frozen. A reader of the outbox should not have to know that one act wrote two rows.
        self._publisher.publish(
            events.dataset_version_created(dataset, version, added=version.members, removed=())
        )
        self._uow.commit()
        return dataset
