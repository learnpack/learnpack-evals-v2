"""Content Registry's Published Language (07-define.md).

`ContentSnapshot` is what Evaluation and Orchestration consume. They never import
`evaluand_registry.domain`.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


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
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"
