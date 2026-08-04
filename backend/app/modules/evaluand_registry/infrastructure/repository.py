"""SQLAlchemy adapters for the Evaluand Registry's ports.

Hand-mapped Core statements keep the domain free of SQLAlchemy (ARCHITECTURE.md §1).
"""

import json
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.generator import GeneratorArtifact, GeneratorVersion
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


class SqlAlchemyGeneratorVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: RowMapping) -> GeneratorVersion:
        return GeneratorVersion(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            metadata=row["metadata"] or {},
        )

    def get_by_id(self, generator_version_id: UUID) -> GeneratorVersion | None:
        row = (
            self._session.execute(
                text("SELECT id, name, version, metadata FROM generator_versions WHERE id = :id"),
                {"id": generator_version_id},
            )
            .mappings()
            .first()
        )
        return None if row is None else self._to_domain(row)

    def exists(self, name: str, version: str) -> bool:
        found = self._session.execute(
            text("SELECT 1 FROM generator_versions WHERE name = :name AND version = :version"),
            {"name": name, "version": version},
        ).first()
        return found is not None

    def add(self, generator: GeneratorVersion) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO generator_versions (id, name, version, metadata)
                VALUES (:id, :name, :version, cast(:metadata as jsonb))
                """
            ),
            {
                "id": generator.id,
                "name": generator.name,
                "version": generator.version,
                "metadata": json.dumps(generator.metadata),
            },
        )

    def list_all(self) -> list[GeneratorVersion]:
        rows = (
            self._session.execute(
                text(
                    "SELECT id, name, version, metadata FROM generator_versions ORDER BY created_at"
                )
            )
            .mappings()
            .all()
        )
        return [self._to_domain(row) for row in rows]


class SqlAlchemyBriefRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: RowMapping) -> GenerationBrief:
        return GenerationBrief(id=row["id"], brief=row["brief"], fields=row["fields"] or {})

    def get_by_id(self, brief_id: UUID) -> GenerationBrief | None:
        row = (
            self._session.execute(
                text("SELECT id, brief, fields FROM generation_briefs WHERE id = :id"),
                {"id": brief_id},
            )
            .mappings()
            .first()
        )
        return None if row is None else self._to_domain(row)

    def add(self, brief: GenerationBrief) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO generation_briefs (id, brief, fields)
                VALUES (:id, :brief, cast(:fields as jsonb))
                """
            ),
            {"id": brief.id, "brief": brief.brief, "fields": json.dumps(brief.fields)},
        )

    def list_all(self) -> list[GenerationBrief]:
        rows = (
            self._session.execute(
                text("SELECT id, brief, fields FROM generation_briefs ORDER BY created_at")
            )
            .mappings()
            .all()
        )
        return [self._to_domain(row) for row in rows]


class SqlAlchemyGeneratorArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, artifact: GeneratorArtifact) -> None:
        self._session.execute(
            text(
                """
                INSERT INTO generator_artifacts (id, generator_version_id, kind, locator, format)
                VALUES (:id, :gvid, :kind, :locator, :format)
                """
            ),
            {
                "id": artifact.id,
                "gvid": artifact.generator_version_id,
                "kind": artifact.kind,
                "locator": artifact.locator,
                "format": artifact.format,
            },
        )

    def list_for_generator(self, generator_version_id: UUID) -> list[GeneratorArtifact]:
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT id, generator_version_id, kind, locator, format
                      FROM generator_artifacts
                     WHERE generator_version_id = :gvid
                     ORDER BY registered_at
                    """
                ),
                {"gvid": generator_version_id},
            )
            .mappings()
            .all()
        )
        return [
            GeneratorArtifact(
                id=row["id"],
                generator_version_id=row["generator_version_id"],
                kind=row["kind"],
                locator=row["locator"],
                format=row["format"],
            )
            for row in rows
        ]


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
