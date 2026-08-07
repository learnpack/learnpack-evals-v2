"""Use case: attribute a generator to an already-registered content (ADR-0024).

The link is a **discovery** — the fact was always true, it is recorded when it is learnt —
so this fills a declared `unknown` and never replaces an existing attribution. The refusal
is stated twice on purpose: the aggregate says the rule where it is read, the repository's
`WHERE generator_version_id IS NULL` holds it under concurrency.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.evaluand_registry.application.ports import (
    ContentRepositoryPort,
    GeneratorVersionRepositoryPort,
)
from app.modules.evaluand_registry.application.register_content_version import (
    UnknownGeneratorVersion,
)
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.content import (
    EducationalContent,
    GeneratorAlreadyAttributed,
)
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class ContentNotFound(Exception):
    """No content version with that id."""


@dataclass(frozen=True)
class AttributeGeneratorCommand:
    content_id: UUID
    generator_version_id: UUID
    attributed_by: UUID


class AttributeGenerator:
    def __init__(
        self,
        contents: ContentRepositoryPort,
        generators: GeneratorVersionRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._contents = contents
        self._generators = generators
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: AttributeGeneratorCommand) -> EducationalContent:
        content = self._contents.get_by_id(command.content_id)
        if content is None:
            raise ContentNotFound(f"content {command.content_id} is not registered")

        # The FK already guarantees integrity; this answers by name instead of by
        # constraint violation (ADR-0024 §7) — ergonomics, not redundancy.
        if self._generators.get_by_id(command.generator_version_id) is None:
            raise UnknownGeneratorVersion(
                f"generator version {command.generator_version_id} is not registered"
            )

        content.attribute_generator(
            generator_version_id=command.generator_version_id,
            attributed_by=command.attributed_by,
            at=datetime.now(UTC),
        )
        if not self._contents.attribute_generator(content):
            raise GeneratorAlreadyAttributed(
                f"content {content.id} was attributed by someone else first"
            )

        self._publisher.publish(events.generator_attributed(content))
        self._uow.commit()
        return content
