"""Use case: register a generation brief — the assignment (13-code-qa §3.2)."""

from dataclasses import dataclass, field
from typing import Any

from app.modules.evaluand_registry.application.ports import BriefRepositoryPort
from app.modules.evaluand_registry.domain import events
from app.modules.evaluand_registry.domain.brief import GenerationBrief
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id


@dataclass(frozen=True)
class RegisterBriefCommand:
    brief: str
    fields: dict[str, Any] = field(default_factory=dict)


class RegisterBrief:
    def __init__(
        self,
        briefs: BriefRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._briefs = briefs
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: RegisterBriefCommand) -> GenerationBrief:
        brief = GenerationBrief(id=new_id(), brief=command.brief, fields=command.fields)

        self._briefs.add(brief)
        # Aggregate + event in the same transaction (ADR-0003).
        self._publisher.publish(events.brief_registered(brief))
        self._uow.commit()
        return brief
