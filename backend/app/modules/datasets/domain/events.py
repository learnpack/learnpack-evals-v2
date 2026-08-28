"""Domain events published by Datasets (ADR-0058).

`DatasetVersionCreated` carries **what changed** — the courses added and the courses removed —
and not only the resulting membership, for the reason ADR-0050 gave: the audit question is
never *what is in this set* (the rows answer that) but *what changed, and who decided*. The
note rides along because a reason nobody can read later is not a reason.
"""

from uuid import UUID

from app.modules.datasets.domain.dataset import Dataset, DatasetVersion
from app.shared.domain.events import DomainEvent

DATASET_AGGREGATE = "Dataset"


def dataset_declared(dataset: Dataset) -> DomainEvent:
    return DomainEvent(
        event_type="DatasetDeclared",
        aggregate_type=DATASET_AGGREGATE,
        aggregate_id=str(dataset.id),
        payload={
            "datasetId": str(dataset.id),
            "name": dataset.name,
            "description": dataset.description,
            "declaredBy": str(dataset.created_by),
        },
    )


def dataset_version_created(
    dataset: Dataset,
    version: DatasetVersion,
    added: tuple[UUID, ...],
    removed: tuple[UUID, ...],
) -> DomainEvent:
    """A membership frozen. Keyed by the dataset, because the version is its child."""
    return DomainEvent(
        event_type="DatasetVersionCreated",
        aggregate_type=DATASET_AGGREGATE,
        aggregate_id=str(dataset.id),
        payload={
            "datasetId": str(dataset.id),
            "datasetVersionId": str(version.id),
            "ordinal": version.ordinal,
            "note": version.note,
            "memberSetHash": version.member_set_hash,
            "memberCount": len(version.members),
            "added": [str(content_id) for content_id in added],
            "removed": [str(content_id) for content_id in removed],
            "createdBy": str(version.created_by),
        },
    )


def dataset_renamed(dataset: Dataset, was: str, renamed_by: UUID) -> DomainEvent:
    """The label, replaced whole — and never a version (ADR-0058 §2).

    `from` and `to`, because a rename is only ever read as a question about what changed.
    """
    return DomainEvent(
        event_type="DatasetRenamed",
        aggregate_type=DATASET_AGGREGATE,
        aggregate_id=str(dataset.id),
        payload={
            "datasetId": str(dataset.id),
            "from": was,
            "to": dataset.name,
            "description": dataset.description,
            "renamedBy": str(renamed_by),
        },
    )
