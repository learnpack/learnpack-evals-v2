"""Use case: register a content version — the generator's work product (13-code-qa §3.2).

The declared surface of the evaluand is the package (ADR-0017): registration captures the
artifacts, never a side metadata channel. `package_format` is an open vocabulary — a new
format is data, and its extraction support is an adapter, not a registry precondition.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.application.ports import (
    BriefRepositoryPort,
    ContentRepositoryPort,
    GeneratorVersionRepositoryPort,
)
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION, EducationalContent
from app.modules.evaluand_registry.domain.package import ContentPackage
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class DuplicateContent(Exception):
    """A content version with the same (packageFormat, externalId, version) exists."""


class BriefNotFound(Exception):
    """The referenced generation brief is not registered."""


class UnknownGeneratorVersion(Exception):
    """The referenced generator version is not registered."""


@dataclass(frozen=True)
class RegisterContentVersionCommand:
    package_format: str
    external_id: str
    consumable_url: str
    version: str = DEFAULT_VERSION
    # {kind, locator, format?} rows — the ContentPackage (open kinds; ADR-0009 evidence).
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"


class RegisterContentVersion:
    def __init__(
        self,
        contents: ContentRepositoryPort,
        briefs: BriefRepositoryPort,
        generators: GeneratorVersionRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._contents = contents
        self._briefs = briefs
        self._generators = generators
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RegisterContentVersionCommand) -> EducationalContent:
        self._require_references(command)

        if self._contents.exists(command.package_format, command.external_id, command.version):
            raise DuplicateContent(
                f"{command.package_format}/{command.external_id} "
                f"version {command.version} is already registered"
            )

        content = EducationalContent(
            id=new_id(),
            package_format=command.package_format,
            external_id=command.external_id,
            consumable_url=command.consumable_url,
            version=command.version,
            package=ContentPackage.validated(command.artifacts),
            brief_id=command.brief_id,
            generator_version_id=command.generator_version_id,
            edit_provenance=command.edit_provenance,
        )

        self._contents.add(content)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.content_version_registered(content))
        self._uow.commit()
        return content

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
