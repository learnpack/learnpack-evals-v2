"""Use case: correct the label, without touching what any round measured (ADR-0058 §2)."""

from dataclasses import dataclass
from uuid import UUID

from app.modules.datasets.application.ports import DatasetRepositoryPort
from app.modules.datasets.domain import events
from app.modules.datasets.domain.dataset import Dataset, DatasetNotFound
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


@dataclass(frozen=True)
class RenameDatasetCommand:
    dataset_id: UUID
    name: str
    renamed_by: UUID
    description: str | None = None


class RenameDataset:
    """Replaces the label whole, and mints no version: a name binds nothing (ADR-0055)."""

    def __init__(
        self,
        datasets: DatasetRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._datasets = datasets
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RenameDatasetCommand) -> Dataset:
        dataset = self._datasets.get(command.dataset_id)
        if dataset is None:
            raise DatasetNotFound(f"dataset {command.dataset_id} is not declared")

        was = dataset.name
        # Raises InvalidDataset on a blank name; returns False when nothing moved.
        if not dataset.rename(command.name, command.description):
            return dataset

        self._datasets.update_label(dataset)
        self._publisher.publish(events.dataset_renamed(dataset, was, command.renamed_by))
        self._uow.commit()
        return dataset
