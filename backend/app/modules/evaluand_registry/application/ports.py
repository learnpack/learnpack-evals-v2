"""Ports required by the Evaluand Registry's use cases. Implemented in infrastructure."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.generator import GeneratorArtifact, GeneratorVersion


class GeneratorVersionRepositoryPort(Protocol):
    def get_by_id(self, generator_version_id: UUID) -> GeneratorVersion | None: ...

    def exists(self, name: str, version: str) -> bool: ...

    def add(self, generator: GeneratorVersion) -> None: ...

    def list_all(self) -> list[GeneratorVersion]: ...


class BriefRepositoryPort(Protocol):
    def get_by_id(self, brief_id: UUID) -> GenerationBrief | None: ...

    def get_by_hash(self, brief_hash: str) -> GenerationBrief | None: ...

    def add(self, brief: GenerationBrief) -> None: ...

    def list_all(self) -> list[GenerationBrief]: ...


@dataclass(frozen=True)
class DerivedBrief:
    """What the intake ACL extracts from a package (ADR-0022): the operative instruction,
    its declared completeness, and the hash identity that dedupes across registrations."""

    brief: str
    fields: dict[str, Any]
    brief_hash: str


class BriefIntakePort(Protocol):
    """Mechanical brief derivation from the package's artifacts (ADR-0022). Returns None
    when the package carries nothing to derive from — best-effort, never blocking."""

    def derive(
        self, package_format: str, artifacts: list[dict[str, Any]]
    ) -> DerivedBrief | None: ...


@dataclass(frozen=True)
class DiscoveredArtifact:
    """One artifact of the declared surface, as discovery found it (ADR-0027)."""

    kind: str
    locator: str
    format: str | None = None


@dataclass(frozen=True)
class DiscoveredPackage:
    """What mechanical discovery read from a package source (ADR-0027): the identity and
    descriptor the package declares, the full artifact list, and the hash of the bytes the
    discovery actually fetched — the content's identity by content."""

    package_format: str
    external_id: str
    title: str | None
    # Only a root that IS the deployed course declares one (ADR-0028): an http root does, a
    # filesystem root never does — serving the bytes is transport, not deployment.
    consumable_url: str | None
    artifacts: tuple[DiscoveredArtifact, ...]
    content_hash: str


class PackageDiscoveryError(Exception):
    """The package could not be mechanically discovered — registration must not proceed.

    Hard-failing on purpose (ADR-0027, contrast with ADR-0022's soft brief intake): a
    mis-discovered package would *be* the evaluand, wrong."""


class PackageDiscoveryPort(Protocol):
    """Mechanical discovery of a package's declared surface from a source locator
    (ADR-0027). Realized per format by the intake ACL; transport is the adapter's axis."""

    def discover(self, package_format: str, source_locator: str) -> DiscoveredPackage: ...


class GeneratorArtifactRepositoryPort(Protocol):
    def add(self, artifact: GeneratorArtifact) -> None: ...

    def list_for_generator(self, generator_version_id: UUID) -> list[GeneratorArtifact]: ...


class ContentRepositoryPort(Protocol):
    def get_by_id(self, content_id: UUID) -> EducationalContent | None: ...

    def exists(self, package_format: str, external_id: str, version: str) -> bool: ...

    def get_by_identity(
        self, package_format: str, external_id: str, version: str
    ) -> EducationalContent | None: ...

    def find_by_logical_and_hash(
        self, package_format: str, external_id: str, content_hash: str
    ) -> EducationalContent | None: ...

    def add(self, content: EducationalContent) -> None: ...

    def attribute_generator(self, content: EducationalContent) -> bool: ...

    def list_all(self) -> list[EducationalContent]: ...

    def list_filtered(
        self,
        package_format: str | None = None,
        brief_ids: list[UUID] | None = None,
        generator_known: bool = False,
    ) -> list[EducationalContent]: ...
