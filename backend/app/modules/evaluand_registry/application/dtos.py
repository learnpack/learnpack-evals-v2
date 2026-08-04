"""Content Registry's Published Language (07-define.md).

`ContentSnapshot` is what Evaluation and Orchestration consume. They never import
`evaluand_registry.domain`.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class MetadataEntryDTO:
    key: str
    value: Any
    value_type: str


@dataclass(frozen=True)
class GeneratorVersionDTO:
    generator_version_id: UUID
    name: str
    version: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class BriefDTO:
    brief_id: UUID
    brief: str
    fields: dict[str, Any]


@dataclass(frozen=True)
class GeneratorArtifactDTO:
    artifact_id: UUID
    generator_version_id: UUID
    kind: str
    locator: str
    format: str | None


@dataclass(frozen=True)
class PackageArtifactDTO:
    kind: str
    locator: str
    format: str | None


@dataclass(frozen=True)
class ContentPackageDTO:
    content_id: UUID
    package_format: str
    consumable_url: str
    artifacts: list[PackageArtifactDTO]


@dataclass(frozen=True)
class ContentSnapshot:
    content_id: UUID
    package_format: str
    external_id: str
    version: str
    consumable_url: str
    metadata: list[MetadataEntryDTO]
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"

    def filtered(self, keys: list[str] | None) -> "ContentSnapshot":
        """Restrict the metadata to a campaign's `metadataView` (ADR-0001).

        Which keys an evaluator sees varies per campaign, so the filtering happens on the
        DTO — the content itself is unchanged.
        """
        if keys is None:
            return self
        allowed = set(keys)
        return ContentSnapshot(
            content_id=self.content_id,
            package_format=self.package_format,
            external_id=self.external_id,
            version=self.version,
            consumable_url=self.consumable_url,
            metadata=[entry for entry in self.metadata if entry.key in allowed],
            brief_id=self.brief_id,
            generator_version_id=self.generator_version_id,
            edit_provenance=self.edit_provenance,
        )
