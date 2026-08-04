"""SQLAlchemy adapters for Content Registry's ports.

Hand-mapped Core statements keep the domain free of SQLAlchemy (ARCHITECTURE.md §1).
"""

import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.metadata import ContentMetadata, MetadataSchema

_COLUMNS = "id, package_format, external_id, version, consumable_url, metadata"


class SqlAlchemyContentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row) -> EducationalContent:  # noqa: ANN001 — RowMapping
        return EducationalContent(
            id=row["id"],
            package_format=row["package_format"],
            external_id=row["external_id"],
            version=row["version"],
            consumable_url=row["consumable_url"],
            # Already persisted: rehydrate without revalidating (the schema may have moved on).
            metadata=ContentMetadata.trusted(row["metadata"] or {}),
        )

    def get_by_id(self, content_id: UUID) -> EducationalContent | None:
        row = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM contents WHERE id = :id"), {"id": content_id}
            )
            .mappings()
            .first()
        )
        return None if row is None else self._to_domain(row)

    def exists(self, package_format: str, external_id: str, version: str) -> bool:
        found = self._session.execute(
            text(
                """
                SELECT 1 FROM contents
                 WHERE package_format = :gs AND external_id = :eid AND version = :v
                """
            ),
            {"gs": package_format, "eid": external_id, "v": version},
        ).first()
        return found is not None

    def add(self, content: EducationalContent) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO contents
                    (id, package_format, external_id, version, consumable_url, metadata)
                VALUES (:id, :gs, :eid, :v, :url, cast(:metadata as jsonb))
                """
            ),
            {
                "id": content.id,
                "gs": content.package_format,
                "eid": content.external_id,
                "v": content.version,
                "url": content.consumable_url,
                "metadata": json.dumps(content.metadata.values),
            },
        )

    def update_metadata(self, content: EducationalContent) -> None:
        self._session.execute(
            text("UPDATE contents SET metadata = cast(:metadata as jsonb) WHERE id = :id"),
            {"id": content.id, "metadata": json.dumps(content.metadata.values)},
        )

    def list_all(self) -> list[EducationalContent]:
        rows = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM contents ORDER BY created_at, external_id")
            )
            .mappings()
            .all()
        )
        return [self._to_domain(row) for row in rows]


class SqlAlchemyMetadataSchemaRepository:
    """Reads the reference data seeded into `metadata_schemas` (ADR-0001)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, package_format: str) -> MetadataSchema | None:
        row = (
            self._session.execute(
                text(
                    """
                    SELECT package_format, spec FROM metadata_schemas
                     WHERE package_format = :gs
                    """
                ),
                {"gs": package_format},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return MetadataSchema.from_spec(row["package_format"], row["spec"])
