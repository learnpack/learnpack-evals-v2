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
from app.modules.evaluand_registry.domain.package import ContentPackage, PackageArtifact

_COLUMNS = (
    "id, package_format, external_id, version, consumable_url, "
    "brief_id, generator_version_id, edit_provenance"
)


class SqlAlchemyContentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: RowMapping, package: ContentPackage) -> EducationalContent:
        return EducationalContent(
            id=row["id"],
            package_format=row["package_format"],
            external_id=row["external_id"],
            version=row["version"],
            consumable_url=row["consumable_url"],
            package=package,
            brief_id=row["brief_id"],
            generator_version_id=row["generator_version_id"],
            edit_provenance=row["edit_provenance"],
        )

    def _packages_for(self, content_ids: list[UUID]) -> dict[UUID, ContentPackage]:
        """One batched read for the child artifact rows — no N+1 (ADR-0006 spirit)."""
        if not content_ids:
            return {}
        rows = (
            self._session.execute(
                text(
                    """
                    SELECT content_id, kind, locator, format
                      FROM content_package_artifacts
                     WHERE content_id = ANY(:ids)
                     ORDER BY content_id, ord
                    """
                ),
                {"ids": content_ids},
            )
            .mappings()
            .all()
        )
        grouped: dict[UUID, list[PackageArtifact]] = {}
        for row in rows:
            grouped.setdefault(row["content_id"], []).append(
                PackageArtifact(kind=row["kind"], locator=row["locator"], format=row["format"])
            )
        return {cid: ContentPackage.trusted(artifacts) for cid, artifacts in grouped.items()}

    def get_by_id(self, content_id: UUID) -> EducationalContent | None:
        row = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM contents WHERE id = :id"), {"id": content_id}
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        packages = self._packages_for([content_id])
        return self._to_domain(row, packages.get(content_id, ContentPackage()))

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
                    (id, package_format, external_id, version, consumable_url,
                     brief_id, generator_version_id, edit_provenance)
                VALUES (:id, :gs, :eid, :v, :url,
                        :brief_id, :gvid, :provenance)
                """
            ),
            {
                "id": content.id,
                "gs": content.package_format,
                "eid": content.external_id,
                "v": content.version,
                "url": content.consumable_url,
                "brief_id": content.brief_id,
                "gvid": content.generator_version_id,
                "provenance": content.edit_provenance,
            },
        )
        for ord_, artifact in enumerate(content.package.artifacts):
            self._session.execute(
                text(
                    """
                    INSERT INTO content_package_artifacts (content_id, ord, kind, locator, format)
                    VALUES (:content_id, :ord, :kind, :locator, :format)
                    """
                ),
                {
                    "content_id": content.id,
                    "ord": ord_,
                    "kind": artifact.kind,
                    "locator": artifact.locator,
                    "format": artifact.format,
                },
            )

    def list_all(self) -> list[EducationalContent]:
        rows = (
            self._session.execute(
                text(f"SELECT {_COLUMNS} FROM contents ORDER BY created_at, external_id")
            )
            .mappings()
            .all()
        )
        packages = self._packages_for([row["id"] for row in rows])
        return [self._to_domain(row, packages.get(row["id"], ContentPackage())) for row in rows]


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
