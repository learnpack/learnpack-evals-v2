"""Use case: give an automated assessor package its identity row (ADR-0016).

An automated assessor exists in code long before it exists in the store: the registry
declares it, and the row appears the first time somebody ratifies it — initial
registration IS the first ratification (ADR-0019 §2). So this is a get-or-create, and its
one refusal is the invariant that gives the row its meaning: a stored `source_config` that
no longer matches the code means the artifact changed without a version bump, and
`(name, version)` would then name two different judges.

It deliberately does **not** commit. Registering and ratifying are one act split across
two modules, wired by the composition root in one transaction (ADR-0036 §3); committing
here would leave a registered assessor behind when the ratification that motivated it is
refused.
"""

from dataclasses import dataclass
from typing import Any

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.ports import AssessorRepositoryPort
from app.modules.identity.application.queries import to_dto
from app.modules.identity.domain.assessor import Assessor, Kind
from app.shared.domain.ids import new_id


class AutomatedAssessorDrifted(Exception):
    """The stored `source_config` differs from the code — bump VERSION (ADR-0016 §2)."""


@dataclass(frozen=True)
class RegisterAutomatedAssessorCommand:
    name: str
    version: str
    display_name: str
    source_config: dict[str, Any]


@dataclass(frozen=True)
class RegisteredAutomatedAssessor:
    assessor: AssessorDTO
    # False when the row was already there: the caller reports registration as an event
    # that happened once, not as something the act does every time.
    newly_registered: bool


class RegisterAutomatedAssessor:
    def __init__(self, assessors: AssessorRepositoryPort) -> None:
        self._assessors = assessors

    def __call__(self, command: RegisterAutomatedAssessorCommand) -> RegisteredAutomatedAssessor:
        existing = self._assessors.get_automated(command.name, command.version)
        if existing is not None:
            if existing.source_config != command.source_config:
                raise AutomatedAssessorDrifted(
                    f"stored source_config of {command.name}:{command.version} differs from "
                    "the code - the artifact changed without a version bump; bump VERSION "
                    "(ADR-0016)"
                )
            return RegisteredAutomatedAssessor(assessor=to_dto(existing), newly_registered=False)

        assessor = Assessor(
            id=new_id(),
            clerk_user_id=None,
            display_name=command.display_name,
            kind=Kind.AUTOMATED,
            source_config=command.source_config,
        )
        self._assessors.add(assessor)
        return RegisteredAutomatedAssessor(assessor=to_dto(assessor), newly_registered=True)
