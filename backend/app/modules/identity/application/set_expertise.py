"""Use case: correct an assessor's expertise profile.

The profile is declared when the invitation is written (ADR-0049) — the only moment anybody
knows it, and the only moment it was ever guaranteed true. It goes stale in the ordinary way:
people change what they work on, and everybody who signed in before invitations existed
carries nothing at all.

**This is not a roster act, and it carries none of their guardrails.** Granting a role and
withdrawing somebody decide what a person may do, so both refuse the two changes nothing
inside the product could undo (ADR-0050, ADR-0051). An expertise profile decides nothing: it
is a fact the roster keeps so a human can pick who should read which course. You may correct
your own, and a deactivated assessor's can be corrected too — their record stays readable, so
it stays truthful.

It is still an event, because somebody typed it and later somebody may want to know who.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.errors import AssessorNotFound, NotAHumanAssessor
from app.modules.identity.application.ports import AssessorRepositoryPort
from app.modules.identity.application.queries import to_dto
from app.modules.identity.domain import events
from app.modules.identity.domain.assessor import Kind
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


@dataclass(frozen=True)
class SetAssessorExpertiseCommand:
    assessor_id: UUID
    expertise: str | None
    changed_by: UUID


class SetAssessorExpertise:
    def __init__(
        self,
        assessors: AssessorRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._assessors = assessors
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: SetAssessorExpertiseCommand) -> AssessorDTO:
        assessor = self._assessors.get_by_id(command.assessor_id)
        if assessor is None:
            raise AssessorNotFound(str(command.assessor_id))
        if assessor.kind is not Kind.HUMAN:
            # An automated assessor's competence is its declared coverage against an
            # instrument (ADR-0018/0019), not a sentence somebody wrote about it.
            raise NotAHumanAssessor(str(command.assessor_id))

        if not assessor.set_expertise(command.expertise):
            # Nothing happened, so nothing is reported — the rule ADR-0050 §3 set.
            return to_dto(assessor)

        self._assessors.update(assessor)
        self._publisher.publish(events.assessor_expertise_changed(assessor, command.changed_by))
        self._uow.commit()
        return to_dto(assessor)
