"""Use case: register a version under a generator — the routine act (ADR-0031 §3).

The lineage arrives as an id, so this act has no name to misspell. It is the one the
genetic-algorithm loop runs many times per generation, which is exactly why the guarding lives
in `RegisterGenerator` and not here: a refusal that fires on every registration stops being read.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.modules.evaluand_registry.application.ports import (
    GeneratorRepositoryPort,
    GeneratorVersionRepositoryPort,
)
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.generator import GeneratorVersion
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class UnknownGenerator(Exception):
    """No lineage with that id. Registering one is a separate, deliberate act — this use case
    never mints a generator, for the same reason mechanical intake never does (ADR-0027)."""


class DuplicateGeneratorVersion(Exception):
    """That version is already registered under that generator — immutable, never edited."""


@dataclass(frozen=True)
class RegisterGeneratorVersionCommand:
    generator_id: UUID
    version: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RegisterGeneratorVersion:
    def __init__(
        self,
        generators: GeneratorRepositoryPort,
        versions: GeneratorVersionRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._generators = generators
        self._versions = versions
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RegisterGeneratorVersionCommand) -> GeneratorVersion:
        generator = self._generators.get_by_id(command.generator_id)
        if generator is None:
            raise UnknownGenerator(f"generator {command.generator_id} is not registered")

        if self._versions.exists(command.generator_id, command.version):
            raise DuplicateGeneratorVersion(
                f"{generator.name} {command.version} is already registered"
            )

        version = GeneratorVersion(
            id=new_id(),
            generator_id=generator.id,
            version=command.version,
            metadata=command.metadata,
        )

        self._versions.add(version)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.generator_version_registered(version, generator))
        self._uow.commit()
        return version
