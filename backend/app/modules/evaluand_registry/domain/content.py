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


class TitleAlreadyRecorded(Exception):
    """The course already carries the name its package declares (ADR-0059 §1): there is no
    act that replaces it, because nobody authored it in the first place."""


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

    `title` is what the package calls itself, read by discovery like the external id and the
    hash (ADR-0059). It describes; `external_id` identifies. Null where the package declares
    none, or where the version predates the column — never derived from the slug, since a name
    made out of an identifier is the defect the field exists to close.
    """

    id: UUID
    package_format: str
    external_id: str
    title: str | None = None
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
        # A blank title is not a title. Normalized rather than refused: a package that
        # declares an empty string has declared nothing, and that is what null says.
        if self.title is not None:
            self.title = self.title.strip() or None
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

    def record_discovered_title(self, title: str) -> None:
        """Keep the name a package declares, for a version registered before the field was
        kept (ADR-0059). One-way, like `attribute_generator` and for the same reason: the
        fact was always true and merely arrived late, so a second write would be somebody
        renaming a course — the act §1 refuses.

        No author and no timestamp, which is where this parts from the two acts around it.
        Nothing about the content changed; the row is catching up with what its package
        always said, and there is no decision to attribute to anyone.
        """
        cleaned = title.strip()
        if not cleaned:
            raise InvalidContent("a recorded title cannot be blank")
        if self.title is not None:
            raise TitleAlreadyRecorded(f"content {self.id} already carries a title")
        self.title = cleaned

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
