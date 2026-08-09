"""Use case: register a content version — the generator's work product (13-code-qa §3.2).

The declared surface of the evaluand is the package (ADR-0017): registration captures the
artifacts, never a side metadata channel. `package_format` is an open vocabulary — a new
format is data, and its extraction support is an adapter, not a registry precondition.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.application.ports import (
    BriefIntakePort,
    BriefRepositoryPort,
    ContentRepositoryPort,
    GeneratorVersionRepositoryPort,
)
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION, EducationalContent
from app.modules.evaluand_registry.domain.package import ContentPackage
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class DuplicateContent(Exception):
    """A content version with the same (packageFormat, externalId, version) exists."""


class UnchangedContent(Exception):
    """The same logical content with an identical content hash is already registered
    (ADR-0027): re-importing it is a no-op, not a duplicate. Carries the existing version
    so callers can report it."""

    def __init__(self, existing: EducationalContent) -> None:
        super().__init__(
            f"{existing.package_format}/{existing.external_id} is already registered "
            f"as version {existing.version} with identical content"
        )
        self.existing = existing


class BriefNotFound(Exception):
    """The referenced generation brief is not registered."""


class UnknownGeneratorVersion(Exception):
    """The referenced generator version is not registered."""


# kw_only so the mandatory declaration below can sit where it belongs semantically
# instead of ahead of the fields that have defaults. Every caller already uses kwargs.
@dataclass(frozen=True, kw_only=True)
class RegisterContentVersionCommand:
    package_format: str
    external_id: str
    # Declares a deployed, human-consumable instance (ADR-0028). Defaulted, unlike the
    # generator link below: silence here means "none declared", it is visible in the console
    # and it costs an empty panel — not an accumulation key the system cannot recover.
    consumable_url: str | None = None
    version: str = DEFAULT_VERSION
    # {kind, locator, format?} rows — the ContentPackage (open kinds; ADR-0009 evidence).
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    brief_id: UUID | None = None
    # No default (ADR-0024): the caller declares a generator version or declares `unknown`
    # by passing None. Silence is not a declaration.
    generator_version_id: UUID | None
    edit_provenance: str = "unknown"
    # Set by mechanical discovery (ADR-0027); None on the hand-registered path, which then
    # dedupes by declared identity only.
    content_hash: str | None = None


class RegisterContentVersion:
    def __init__(
        self,
        contents: ContentRepositoryPort,
        briefs: BriefRepositoryPort,
        generators: GeneratorVersionRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
        brief_intake: BriefIntakePort | None = None,
    ) -> None:
        self._contents = contents
        self._briefs = briefs
        self._generators = generators
        self._publisher = publisher
        self._uow = uow
        self._brief_intake = brief_intake

    def __call__(self, command: RegisterContentVersionCommand) -> EducationalContent:
        self._require_references(command)

        if command.content_hash is not None:
            same = self._contents.find_by_logical_and_hash(
                command.package_format, command.external_id, command.content_hash
            )
            if same is not None:
                raise UnchangedContent(same)

        existing = self._contents.get_by_identity(
            command.package_format, command.external_id, command.version
        )
        if existing is not None:
            message = (
                f"{command.package_format}/{command.external_id} "
                f"version {command.version} is already registered"
            )
            if (
                command.content_hash is not None
                and existing.content_hash is not None
                and existing.content_hash != command.content_hash
            ):
                message += (
                    " and the package content differs from what that version registered"
                    " — declare a new version"
                )
            raise DuplicateContent(message)

        content = EducationalContent(
            id=new_id(),
            package_format=command.package_format,
            external_id=command.external_id,
            consumable_url=command.consumable_url,
            version=command.version,
            package=ContentPackage.validated(command.artifacts),
            brief_id=self._resolve_brief(command),
            generator_version_id=command.generator_version_id,
            edit_provenance=command.edit_provenance,
            content_hash=command.content_hash,
        )

        self._contents.add(content)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.content_version_registered(content))
        self._uow.commit()
        return content

    def _resolve_brief(self, command: RegisterContentVersionCommand) -> UUID | None:
        """An explicit brief wins; otherwise the intake ACL derives one from the package,
        deduped by hash identity (ADR-0022). Same transaction as the registration."""
        if command.brief_id is not None or self._brief_intake is None:
            return command.brief_id

        derived = self._brief_intake.derive(command.package_format, command.artifacts)
        if derived is None:
            return None  # registered absent — a first-class recorded state

        existing = self._briefs.get_by_hash(derived.brief_hash)
        if existing is not None:
            return existing.id  # same effective instruction → same brief (pairing)

        brief = GenerationBrief(
            id=new_id(),
            brief=derived.brief,
            fields=derived.fields,
            brief_hash=derived.brief_hash,
        )
        self._briefs.add(brief)
        self._publisher.publish(events.brief_registered(brief))
        return brief.id

    def _require_references(self, command: RegisterContentVersionCommand) -> None:
        # App-level referential validation (cross-aggregate; 13-code-qa §2 pattern).
        if command.brief_id is not None and self._briefs.get_by_id(command.brief_id) is None:
            raise BriefNotFound(f"brief {command.brief_id} is not registered")
        if (
            command.generator_version_id is not None
            and self._generators.get_by_id(command.generator_version_id) is None
        ):
            raise UnknownGeneratorVersion(
                f"generator version {command.generator_version_id} is not registered"
            )
