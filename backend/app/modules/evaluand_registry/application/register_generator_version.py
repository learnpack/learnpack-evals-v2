"""Use case: declare a generator version — the examinee's identity (13-code-qa §3.2)."""

from dataclasses import dataclass, field
from typing import Any

from app.modules.evaluand_registry.application.ports import GeneratorVersionRepositoryPort
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.generator import GeneratorVersion
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class DuplicateGeneratorVersion(Exception):
    """That (name, version) identity is already registered — immutable, never edited."""


@dataclass(frozen=True)
class RegisterGeneratorVersionCommand:
    name: str
    version: str
    metadata: dict[str, Any] = field(default_factory=dict)


class RegisterGeneratorVersion:
    def __init__(
        self,
        generators: GeneratorVersionRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._generators = generators
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RegisterGeneratorVersionCommand) -> GeneratorVersion:
        if self._generators.exists(command.name, command.version):
            raise DuplicateGeneratorVersion(
                f"{command.name} {command.version} is already registered"
            )

        generator = GeneratorVersion(
            id=new_id(),
            name=command.name,
            version=command.version,
            metadata=command.metadata,
        )

        self._generators.add(generator)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.generator_version_registered(generator))
        self._uow.commit()
        return generator
