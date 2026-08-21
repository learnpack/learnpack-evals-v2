"""Use case: grant or withdraw a role (ADR-0050).

The invariant this must not break is the one ADR-0007 wrote a test for: **logging in cannot
escalate a privilege**. That is a statement about authentication, not about administration —
an admin-only act, taken deliberately, with an author recorded and a refusal for the two ways
it goes wrong, does not weaken it. The CLI keeps `set-role` as break-glass.

The two guardrails are not hypothetical. Demoting the last admin locks the console for
everybody, with no screen left that could undo it; changing your own role is how somebody
does that to themselves in one click while meaning to fix a list.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.errors import AssessorNotFound, NotAHumanAssessor
from app.modules.identity.application.ports import AssessorRepositoryPort
from app.modules.identity.application.queries import to_dto
from app.modules.identity.domain import events
from app.modules.identity.domain.assessor import Kind, Role
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort


class CannotChangeOwnRole(Exception):
    """Somebody else grants you a role. Doing it to yourself is either pointless or the
    accident this refuses — an admin removing their own last admin."""


class CannotDemoteLastAdmin(Exception):
    """There would be nobody left who can grant it back, and no screen that could."""


@dataclass(frozen=True)
class ChangeAssessorRoleCommand:
    assessor_id: UUID
    role: Role
    changed_by: UUID


class ChangeAssessorRole:
    def __init__(
        self,
        assessors: AssessorRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._assessors = assessors
        self._publisher = publisher
        self._uow = uow

    def __call__(self, command: ChangeAssessorRoleCommand) -> AssessorDTO:
        assessor = self._assessors.get_by_id(command.assessor_id)
        if assessor is None:
            raise AssessorNotFound(str(command.assessor_id))
        if assessor.kind is not Kind.HUMAN:
            raise NotAHumanAssessor(str(command.assessor_id))
        if assessor.id == command.changed_by:
            raise CannotChangeOwnRole(str(command.assessor_id))

        was = assessor.role
        if was is command.role:
            # Not a refusal and not an event: nothing happened. Reporting a role change that
            # changed no role would put a fact in the outbox that never occurred.
            return to_dto(assessor)

        if was is Role.ADMIN and self._assessors.count_admins() <= 1:
            raise CannotDemoteLastAdmin(str(command.assessor_id))

        assessor.assign_role(command.role)
        self._assessors.update(assessor)
        self._publisher.publish(events.assessor_role_changed(assessor, was, command.changed_by))
        self._uow.commit()
        return to_dto(assessor)
