"""Published Language of Content Profiling — plain, immutable data (ARCHITECTURE.md §3).

`PackageDTO`/`ArtifactDTO` are this module's OWN input shapes: the application layer never
imports another module's types, so the gateway (infrastructure) translates the registry's
`ContentPackageDTO` into these at the boundary (Conformist, with local types).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ArtifactDTO:
    kind: str
    locator: str
    format: str | None = None


@dataclass(frozen=True)
class PackageDTO:
    """What the extraction adapter reads: the work product plus its declared metadata."""

    content_id: UUID
    package_format: str
    consumable_url: str
    artifacts: tuple[ArtifactDTO, ...] = ()
    declared_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfileEntrySnapshot:
    data_requirement_id: str
    provenance: str
    value: Any
    quote: str | None
    locator: dict[str, Any] | None


@dataclass(frozen=True)
class ProfileExtraSnapshot:
    name: str
    value: Any
    quote: str | None
    locator: dict[str, Any] | None


@dataclass(frozen=True)
class ContentProfileSnapshot:
    """A profile as consumers see it — self-contained, citations included (ADR-0009)."""

    profile_id: UUID
    content_id: UUID
    package_format: str
    adapter_version: str
    status: str
    error: str | None
    profiled_at: datetime | None
    entries: tuple[ProfileEntrySnapshot, ...] = ()
    extras: tuple[ProfileExtraSnapshot, ...] = ()
