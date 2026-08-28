"""Ports required by Datasets. Implemented in infrastructure."""

from typing import Protocol
from uuid import UUID

from app.modules.datasets.domain.dataset import Dataset, DatasetVersion


class DatasetRepositoryPort(Protocol):
    def get(self, dataset_id: UUID) -> Dataset | None: ...

    def list_all(self) -> list[Dataset]: ...

    def find_dataset_of_version(self, version_id: UUID) -> Dataset | None:
        """The dataset a version belongs to — a version is reached through its root."""
        ...

    def add(self, dataset: Dataset) -> None:
        """Write the dataset and the version it was declared with, in one act."""
        ...

    def append_version(self, dataset_id: UUID, version: DatasetVersion) -> None:
        """Add one version. Never rewrites the ones already there — they are immutable."""
        ...

    def update_label(self, dataset: Dataset) -> None:
        """Name and description only: the membership is not reachable from a rename."""
        ...
