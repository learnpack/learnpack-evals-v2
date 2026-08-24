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

    `consumable_url` is nullable for a different reason (ADR-0028): it declares that a
    deployed, human-consumable instance of this version exists — a fact about the world
    outside this system, which no discovery can produce. Without it the version is still a
    complete evaluand: the profile is built from the artifact locators, never from this URL.
    What a null closes is the human path.
    """

    id: UUID
    package_format: str
    external_id: str
    consumable_url: str | None = None
    version: str = DEFAULT_VERSION
    package: ContentPackage = field(default_factory=ContentPackage)
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"
    # Hash of the discovered artifact bytes (ADR-0027) — the content's identity by content.
    # None when the version was registered by hand, without mechanical discovery.
    content_hash: str | None = None
    # Set only when the link was filled after registration (ADR-0024): null on both means
    # the generator was declared when the content was registered.
    generator_attributed_by: UUID | None = None
    generator_attributed_at: datetime | None = None
    # The same reading for the deployment (ADR-0054): null on both means the URL — if there
    # is one — came from registration rather than from a later act. The last act, not a
    # history; the history is `ConsumableUrlDeclared` in the outbox.
    consumable_url_declared_by: UUID | None = None
    consumable_url_declared_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.package_format or not self.package_format.strip():
            raise InvalidContent("package_format is required")
        if not self.external_id or not self.external_id.strip():
            raise InvalidContent("external_id is required")
        if not self.version or not self.version.strip():
            raise InvalidContent("version is required")
        # A declaration that a deployed, human-consumable instance exists (ADR-0028) — not a
        # way to reach the package's bytes; those are the artifact locators. None declares
        # none; a blank is never coerced into one, so a caller that means "none" says so.
        if self.consumable_url is not None and not self.consumable_url.startswith(
            ("http://", "https://")
        ):
            raise InvalidContent("consumable_url must be an http(s) URL when declared")
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

    def declare_consumable_url(self, url: str, declared_by: UUID, at: datetime) -> bool:
        """Declare the deployment of an already-registered version (ADR-0054).

        **Repeatable**, and that is where this parts from `attribute_generator`: a generator
        link is a discovery — the fact was always true — while a deployment is a statement
        about the world right now. A course moves, comes down, is redeployed; a declaration
        that could be made only once would leave a dead link with no repair.

        Returns whether anything changed, so the caller can keep a no-op out of the outbox
        (ADR-0054 §3). Clearing is refused rather than silently allowed: `None` already means
        *none declared* in this column, and writing it would need an answer about the
        evaluations already produced against the old URL that nothing consumes yet.
        """
        if url is None or not url.startswith(("http://", "https://")):
            raise InvalidContent("consumable_url must be an http(s) URL when declared")
        if url == self.consumable_url:
            return False
        self.consumable_url = url
        self.consumable_url_declared_by = declared_by
        self.consumable_url_declared_at = at
        return True

    @property
    def logical_id(self) -> tuple[str, str]:
        """The logical content this version belongs to."""
        return (self.package_format, self.external_id)
