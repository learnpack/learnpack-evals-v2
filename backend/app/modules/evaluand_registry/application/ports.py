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


class GeneratorArtifactRepositoryPort(Protocol):
    def add(self, artifact: GeneratorArtifact) -> None: ...

    def list_for_generator(self, generator_version_id: UUID) -> list[GeneratorArtifact]: ...


class ContentRepositoryPort(Protocol):
    def get_by_id(self, content_id: UUID) -> EducationalContent | None: ...

    def exists(self, package_format: str, external_id: str, version: str) -> bool: ...

    def add(self, content: EducationalContent) -> None: ...

    def attribute_generator(self, content: EducationalContent) -> bool: ...

    def list_all(self) -> list[EducationalContent]: ...

    def list_filtered(
        self,
        package_format: str | None = None,
        brief_ids: list[UUID] | None = None,
        generator_known: bool = False,
    ) -> list[EducationalContent]: ...
