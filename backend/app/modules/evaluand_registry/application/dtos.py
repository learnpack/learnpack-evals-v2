"""Content Registry's Published Language (07-define.md).

`ContentSnapshot` is what Evaluation and Orchestration consume. They never import
`evaluand_registry.domain`.
"""

from dataclasses import dataclass
from datetime import datetime
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
class PackageArtifactDTO:
    kind: str
    locator: str
    format: str | None


@dataclass(frozen=True)
class ContentPackageDTO:
    content_id: UUID
    package_format: str
    # None when no deployed, human-consumable instance is declared (ADR-0028). Undefaulted
    # on purpose: inputs may omit it, outputs always state it — possibly null.
    consumable_url: str | None
    artifacts: list[PackageArtifactDTO]


@dataclass(frozen=True)
class ContentSnapshot:
    content_id: UUID
    package_format: str
    external_id: str
    version: str
    # None when no deployed, human-consumable instance is declared (ADR-0028): the content is
    # a complete evaluand for the automated path, and cannot be handed to a human evaluator.
    consumable_url: str | None
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"
    # Set only when the generator was attributed after registration (ADR-0024).
    generator_attributed_by: UUID | None = None
    generator_attributed_at: datetime | None = None
