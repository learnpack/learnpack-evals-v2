"""`EducationalContent` aggregate — pure Python.

Every instance is a concrete **version**: `id` (contentId) identifies a version, while the
logical content is `(generating_system, external_id)`. Evaluating v1 vs v2 of the same course
is a first-class case (ADR-0005).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.domain.metadata import ContentMetadata, MetadataSchema

DEFAULT_VERSION = "1"


class InvalidContent(Exception):
    """The content breaks an invariant of its aggregate."""


@dataclass
class EducationalContent:
    """Aggregate root. Owns its `ContentMetadata`."""

    id: UUID
    generating_system: str
    external_id: str
    consumable_url: str
    version: str = DEFAULT_VERSION
    metadata: ContentMetadata = field(default_factory=lambda: ContentMetadata(values={}))

    def __post_init__(self) -> None:
        if not self.generating_system or not self.generating_system.strip():
            raise InvalidContent("generating_system is required")
        if not self.external_id or not self.external_id.strip():
            raise InvalidContent("external_id is required")
        if not self.version or not self.version.strip():
            raise InvalidContent("version is required")
        # The evaluator has to be able to consume the content (07-define.md).
        if not self.consumable_url or not self.consumable_url.strip():
            raise InvalidContent("consumable_url is required")
        if not self.consumable_url.startswith(("http://", "https://")):
            raise InvalidContent("consumable_url must be an http(s) URL")

    @property
    def logical_id(self) -> tuple[str, str]:
        """The logical content this version belongs to."""
        return (self.generating_system, self.external_id)

    def update_metadata(self, values: dict[str, Any], schema: MetadataSchema) -> None:
        """Replace the metadata, revalidating against the schema."""
        self.metadata = ContentMetadata.validated(values, schema)
