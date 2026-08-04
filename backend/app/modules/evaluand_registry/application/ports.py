"""Ports required by Content Registry's use cases. Implemented in infrastructure."""

from typing import Protocol
from uuid import UUID

from app.modules.evaluand_registry.domain.content import EducationalContent
from app.modules.evaluand_registry.domain.metadata import MetadataSchema


class ContentRepositoryPort(Protocol):
    def get_by_id(self, content_id: UUID) -> EducationalContent | None: ...

    def exists(self, package_format: str, external_id: str, version: str) -> bool: ...

    def add(self, content: EducationalContent) -> None: ...

    def update_metadata(self, content: EducationalContent) -> None: ...

    def list_all(self) -> list[EducationalContent]: ...


class MetadataSchemaRepositoryPort(Protocol):
    def get(self, package_format: str) -> MetadataSchema | None: ...
