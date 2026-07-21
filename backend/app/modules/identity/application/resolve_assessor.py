"""Resolve a verified Clerk identity into our own `Assessor` (ADR-0004).

Entry point of every authenticated request: on first login the assessor is created; later
logins only refresh the profile. The role is deliberately never touched here — promotion is
the CLI's job, so a login can never escalate privileges.
"""

from dataclasses import dataclass

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.ports import AssessorRepositoryPort
from app.modules.identity.domain.assessor import Assessor, Role
from app.shared.application.ports import UnitOfWorkPort
from app.shared.domain.ids import new_id


@dataclass(frozen=True)
class ClerkIdentity:
    """The claims we care about, already verified by the Clerk adapter."""

    clerk_user_id: str
    email: str | None = None
    display_name: str | None = None


class ResolveAssessor:
    def __init__(self, assessors: AssessorRepositoryPort, uow: UnitOfWorkPort) -> None:
        self._assessors = assessors
        self._uow = uow

    def __call__(self, identity: ClerkIdentity) -> AssessorDTO:
        assessor = self._assessors.get_by_clerk_user_id(identity.clerk_user_id)

        if assessor is None:
            assessor = Assessor(
                id=new_id(),
                clerk_user_id=identity.clerk_user_id,
                email=identity.email,
                display_name=identity.display_name,
                role=Role.EVALUATOR,
            )
            self._assessors.add(assessor)
            self._uow.commit()
        elif assessor.update_profile(identity.email, identity.display_name):
            self._assessors.update(assessor)
            self._uow.commit()

        return AssessorDTO(
            assessor_id=assessor.id,
            role=str(assessor.role),
            email=assessor.email,
            display_name=assessor.display_name,
        )
