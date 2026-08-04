"""Use case: register a generator-level artifact.

Registered now, profiled only when a claim needs it (first-increment mark, 13-code-qa).
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluand_registry.application.ports import (
    GeneratorArtifactRepositoryPort,
    GeneratorVersionRepositoryPort,
)
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.generator import GeneratorArtifact
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class GeneratorVersionNotFound(Exception):
    """The referenced generator version is not registered."""


@dataclass(frozen=True)
class RegisterGeneratorArtifactCommand:
    generator_version_id: UUID
    kind: str
    locator: str
    format: str | None = None


class RegisterGeneratorArtifact:
    def __init__(
        self,
        generators: GeneratorVersionRepositoryPort,
        artifacts: GeneratorArtifactRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._generators = generators
        self._artifacts = artifacts
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RegisterGeneratorArtifactCommand) -> GeneratorArtifact:
        if self._generators.get_by_id(command.generator_version_id) is None:
            raise GeneratorVersionNotFound(
                f"generator version {command.generator_version_id} is not registered"
            )

        artifact = GeneratorArtifact(
            id=new_id(),
            generator_version_id=command.generator_version_id,
            kind=command.kind,
            locator=command.locator,
            format=command.format,
        )

        self._artifacts.add(artifact)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.generator_artifact_registered(artifact))
        self._uow.commit()
        return artifact
