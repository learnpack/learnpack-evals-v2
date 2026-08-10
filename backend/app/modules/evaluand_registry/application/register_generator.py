"""Use case: mint a generator lineage — the rare act (ADR-0031 §3).

This is the one gate in the system where a generator name is still typed, so it is the one gate
that is guarded. Everything downstream — registering a version, declaring a content's generator,
resolving a `courses/` folder — selects an id and can no longer misspell anything.
"""

from dataclasses import dataclass

from app.modules.evaluand_registry.application.ports import GeneratorRepositoryPort
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.generator import (
    Generator,
    canonical_name,
    nearest_name,
    normalized_name,
)
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


class DuplicateGenerator(Exception):
    """That name is already registered. Not a near miss and not overridable — the normalized
    key is the identity, so this *is* the same lineage."""


class SimilarGeneratorExists(Exception):
    """The name is close enough to a registered one to be a typo of it. Overridable, because
    only a human can tell a typo from a genuinely new generator with a similar name."""

    def __init__(self, candidate: str, existing: str) -> None:
        self.candidate = candidate
        self.existing = existing
        super().__init__(
            f"'{candidate}' is one or two edits from the registered generator '{existing}' — "
            f"if it is a different generator, confirm it by declaring it distinct from "
            f"'{existing}'"
        )


@dataclass(frozen=True)
class RegisterGeneratorCommand:
    name: str
    confirm_distinct_from: str | None = None
    """Echo of the name the guard named. A boolean would be passed by any retry, including a
    blind one and including a script carrying it permanently; an echo can only be supplied by
    someone who read this particular answer (ADR-0031 §4)."""


class RegisterGenerator:
    def __init__(
        self,
        generators: GeneratorRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._generators = generators
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RegisterGeneratorCommand) -> Generator:
        name = " ".join(command.name.split())
        registered = self._generators.list_all()

        if self._generators.find_by_name_key(normalized_name(name)) is not None:
            raise DuplicateGenerator(f"generator '{name}' is already registered")

        similar = nearest_name(name, [g.name for g in registered])
        if similar is not None and not self._confirms(command.confirm_distinct_from, similar):
            raise SimilarGeneratorExists(candidate=name, existing=similar)

        generator = Generator(id=new_id(), name=name)
        self._generators.add(generator)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.generator_registered(generator))
        self._uow.commit()
        return generator

    @staticmethod
    def _confirms(echoed: str | None, named: str) -> bool:
        """The confirmation has to name the generator the guard actually named. Compared on the
        canonical form so the caller may retype it without matching its spacing — what is being
        proven is that a human read the answer, not that they can copy a string."""
        return echoed is not None and canonical_name(echoed) == canonical_name(named)
