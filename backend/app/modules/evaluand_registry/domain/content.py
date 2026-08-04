"""`EducationalContent` aggregate — pure Python.

Every instance is a concrete **version**: `id` (contentId) identifies a version, while the
logical content is `(package_format, external_id)`. Evaluating v1 vs v2 of the same course
is a first-class case (ADR-0005).
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.domain.metadata import ContentMetadata, MetadataSchema
from app.modules.evaluand_registry.domain.package import ContentPackage

DEFAULT_VERSION = "1"

# Edit provenance of a version (GLOSSARY): pure generator output, human-touched, or unknown.
EDIT_PROVENANCES = ("pure", "human_edited", "unknown")


class InvalidContent(Exception):
    """The content breaks an invariant of its aggregate."""


@dataclass
class EducationalContent:
    """Aggregate root. Owns its `ContentMetadata` and its `ContentPackage`.

    `brief_id`/`generator_version_id` are nullable on purpose: an absent brief is
    *recorded* absent, and a null generator means `unknown` — valid for content-level
    judgments, excluded from generator-level accumulation (design 12 §Registry).
    """

    id: UUID
    package_format: str
    external_id: str
    consumable_url: str
    version: str = DEFAULT_VERSION
    metadata: ContentMetadata = field(default_factory=lambda: ContentMetadata(values={}))
    package: ContentPackage = field(default_factory=ContentPackage)
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"

    def __post_init__(self) -> None:
        if not self.package_format or not self.package_format.strip():
            raise InvalidContent("package_format is required")
        if not self.external_id or not self.external_id.strip():
            raise InvalidContent("external_id is required")
        if not self.version or not self.version.strip():
            raise InvalidContent("version is required")
        # The evaluator has to be able to consume the content (07-define.md).
        if not self.consumable_url or not self.consumable_url.strip():
            raise InvalidContent("consumable_url is required")
        if not self.consumable_url.startswith(("http://", "https://")):
            raise InvalidContent("consumable_url must be an http(s) URL")
        if self.edit_provenance not in EDIT_PROVENANCES:
            raise InvalidContent(f"edit_provenance must be one of {', '.join(EDIT_PROVENANCES)}")

    @property
    def logical_id(self) -> tuple[str, str]:
        """The logical content this version belongs to."""
        return (self.package_format, self.external_id)

    def update_metadata(self, values: dict[str, Any], schema: MetadataSchema) -> None:
        """Replace the metadata, revalidating against the schema."""
        self.metadata = ContentMetadata.validated(values, schema)
