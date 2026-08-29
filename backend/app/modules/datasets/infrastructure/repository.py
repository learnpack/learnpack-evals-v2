"""SQLAlchemy adapter for `DatasetRepositoryPort`.

Hand-mapped Core statements keep the domain free of SQLAlchemy (ARCHITECTURE.md §1). Versions
and their members are children of the aggregate and are **appended, never rewritten**: a
version is immutable, so the `update`-by-replace shape the studies repository uses would be
the wrong verb here.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.modules.datasets.domain.dataset import Dataset, DatasetVersion

_DATASET_COLUMNS = "id, name, description, created_by, created_at"
_VERSION_COLUMNS = "id, dataset_id, ordinal, note, member_set_hash, created_by, created_at"


class SqlAlchemyDatasetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_version(row: RowMapping, members: tuple[UUID, ...]) -> DatasetVersion:
        return DatasetVersion(
            id=row["id"],
            ordinal=row["ordinal"],
            note=row["note"],
            members=members,
            member_set_hash=row["member_set_hash"],
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    def _versions_for(self, dataset_ids: list[UUID]) -> dict[UUID, tuple[DatasetVersion, ...]]:
        """Two batched reads for the whole child tree — no N+1 (ADR-0006 spirit)."""
        if not dataset_ids:
            return {}

        version_rows = (
            self._session.execute(
                text(
                    f"SELECT {_VERSION_COLUMNS} FROM dataset_versions "
                    "WHERE dataset_id = ANY(:ids) ORDER BY dataset_id, ordinal"
                ),
                {"ids": dataset_ids},
            )
            .mappings()
            .all()
        )
        member_rows = self._session.execute(
            text(
                "SELECT dataset_version_id, content_id FROM dataset_version_members "
                "WHERE dataset_version_id = ANY(:ids) ORDER BY content_id"
            ),
            {"ids": [row["id"] for row in version_rows]},
        ).all()

        members: dict[UUID, list[UUID]] = defaultdict(list)
        for version_id, content_id in member_rows:
            members[version_id].append(content_id)

        by_dataset: dict[UUID, list[DatasetVersion]] = defaultdict(list)
        for row in version_rows:
            by_dataset[row["dataset_id"]].append(self._to_version(row, tuple(members[row["id"]])))
        return {dataset_id: tuple(found) for dataset_id, found in by_dataset.items()}

    def _hydrate(self, rows: list[RowMapping]) -> list[Dataset]:
        versions = self._versions_for([row["id"] for row in rows])
        return [
            Dataset(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                created_by=row["created_by"],
                versions=versions.get(row["id"], ()),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get(self, dataset_id: UUID) -> Dataset | None:
        row = (
            self._session.execute(
                text(f"SELECT {_DATASET_COLUMNS} FROM datasets WHERE id = :id"),
                {"id": dataset_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return self._hydrate([row])[0]

    def find_dataset_of_version(self, version_id: UUID) -> Dataset | None:
        """The dataset a version belongs to, hydrated whole.

        A version is a child of the aggregate, so it is reached through its root rather than
        read on its own — and the root is what carries the name a consumer wants to show.
        """
        dataset_id = self._session.execute(
            text("SELECT dataset_id FROM dataset_versions WHERE id = :id"),
            {"id": version_id},
        ).scalar()
        return None if dataset_id is None else self.get(dataset_id)

    def list_all(self) -> list[Dataset]:
        rows = (
            self._session.execute(
                text(f"SELECT {_DATASET_COLUMNS} FROM datasets ORDER BY created_at")
            )
            .mappings()
            .all()
        )
        return self._hydrate(list(rows))

    def add(self, dataset: Dataset) -> None:
        # `COALESCE(..., now())` and not the column default alone: the act stamps the time it
        # happened and returns it, so writing the server's clock instead would answer the
        # create and the next read with two different times for one fact.
        self._session.execute(
            text(
                """
                INSERT INTO datasets (id, name, description, created_by, created_at)
                VALUES (:id, :name, :description, :created_by, COALESCE(:created_at, now()))
                """
            ),
            {
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "created_by": dataset.created_by,
                "created_at": dataset.created_at,
            },
        )
        for version in dataset.versions:
            self.append_version(dataset.id, version)

    def append_version(self, dataset_id: UUID, version: DatasetVersion) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO dataset_versions
                    (id, dataset_id, ordinal, note, member_set_hash, created_by, created_at)
                VALUES (:id, :dataset_id, :ordinal, :note, :member_set_hash, :created_by,
                        COALESCE(:created_at, now()))
                """
            ),
            {
                "id": version.id,
                "dataset_id": dataset_id,
                "ordinal": version.ordinal,
                "note": version.note,
                "member_set_hash": version.member_set_hash,
                "created_by": version.created_by,
                "created_at": version.created_at,
            },
        )
        for content_id in version.members:
            self._session.execute(
                text(
                    """
                    INSERT INTO dataset_version_members (dataset_version_id, content_id)
                    VALUES (:version_id, :content_id)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {"version_id": version.id, "content_id": content_id},
            )

    def update_label(self, dataset: Dataset) -> None:
        self._session.execute(
            text("UPDATE datasets SET name = :name, description = :description WHERE id = :id"),
            {"id": dataset.id, "name": dataset.name, "description": dataset.description},
        )
