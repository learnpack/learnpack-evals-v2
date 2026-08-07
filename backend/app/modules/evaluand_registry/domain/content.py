"""`EducationalContent` aggregate — pure Python.

Every instance is a concrete **version**: `id` (contentId) identifies a version, while the
logical content is `(package_format, external_id)`. Evaluating v1 vs v2 of the same course
is a first-class case (ADR-0005).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.modules.evaluand_registry.domain.package import ContentPackage

DEFAULT_VERSION = "1"

# Edit provenance of a version (GLOSSARY): pure generator output, human-touched, or unknown.
EDIT_PROVENANCES = ("pure", "human_edited", "unknown")


class InvalidContent(Exception):
    """The content breaks an invariant of its aggregate."""


class GeneratorAlreadyAttributed(Exception):
    """The generator link is already known: `unknown → known` is a discovery,
    `known → other known` would rewrite what was declared (ADR-0024)."""


@dataclass
class EducationalContent:
    """Aggregate root. Owns its `ContentPackage` — the declared surface of the evaluand
    (ADR-0017): whatever the platform or generator declares travels as package artifacts,
    never as a side metadata channel.

    `brief_id`/`generator_version_id` are nullable on purpose: an absent brief is
    *recorded* absent, and a null generator means `unknown` — valid for content-level
    judgments, excluded from generator-level accumulation (design 12 §Registry).
    """

    id: UUID
    package_format: str
    external_id: str
    consumable_url: str
    version: str = DEFAULT_VERSION
    package: ContentPackage = field(default_factory=ContentPackage)
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"
    # Set only when the link was filled after registration (ADR-0024): null on both means
    # the generator was declared when the content was registered.
    generator_attributed_by: UUID | None = None
    generator_attributed_at: datetime | None = None

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

    def attribute_generator(
        self, generator_version_id: UUID, attributed_by: UUID, at: datetime
    ) -> None:
        """Record a generator discovered after registration (ADR-0024). One-way: it fills a
        declared void, it never replaces an attribution. `edit_provenance` is orthogonal —
        human-edited content is still attributable to whatever produced the first draft."""
        if self.generator_version_id is not None:
            raise GeneratorAlreadyAttributed(
                f"content {self.id} is already attributed to generator {self.generator_version_id}"
            )
        self.generator_version_id = generator_version_id
        self.generator_attributed_by = attributed_by
        self.generator_attributed_at = at

    @property
    def logical_id(self) -> tuple[str, str]:
        """The logical content this version belongs to."""
        return (self.package_format, self.external_id)
