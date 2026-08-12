"""Resolve a verified Clerk identity into our own `Assessor` (ADR-0004).

Entry point of every authenticated request: on first login the assessor is created; later
logins only refresh the profile. The role is deliberately never touched here — promotion is
the CLI's job, so a login can never escalate privileges.
"""

from collections.abc import Iterable
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
    def __init__(
        self,
        assessors: AssessorRepositoryPort,
        uow: UnitOfWorkPort,
        bootstrap_admins: Iterable[str] = (),
    ) -> None:
        self._assessors = assessors
        self._uow = uow
        # Provisioning allowlist, NOT an authorisation source — see `_initial_role`.
        self._bootstrap_admins = frozenset(e.strip().lower() for e in bootstrap_admins if e)

    def __call__(self, identity: ClerkIdentity) -> AssessorDTO:
        assessor = self._assessors.get_by_clerk_user_id(identity.clerk_user_id)

        if assessor is None:
            assessor = Assessor(
                id=new_id(),
                clerk_user_id=identity.clerk_user_id,
                email=identity.email,
                display_name=identity.display_name,
                role=self._initial_role(identity.email),
            )
            self._assessors.add(assessor)
            self._uow.commit()
        elif assessor.update_profile(identity.email, identity.display_name):
            # Note what is *not* here: the role. An existing assessor's role never changes
            # on login, whatever the allowlist says — logging in cannot escalate privileges.
            self._assessors.update(assessor)
            self._uow.commit()

        return AssessorDTO(
            assessor_id=assessor.id,
            role=str(assessor.role),
            email=assessor.email,
            display_name=assessor.display_name,
            # Always `human` on this path — an automated assessor has no credential to
            # arrive with (ADR-0016) — but stated rather than defaulted.
            kind=str(assessor.kind),
        )

    def _initial_role(self, email: str | None) -> Role:
        """The role a brand-new assessor is created with.

        The allowlist solves bootstrapping only: someone has to be able to register content
        and open a campaign before any admin exists to run `set-role`. It applies **at
        creation and never again**, so `assessors.role` stays the single source of truth
        and the allowlist behaves like a default, not like a permission.

        Safe because access is invite-only (ADR-0004): an attacker cannot sign up with an
        admin's address, they would need the invitation. If invite-only were ever turned
        off, this would become an escalation path — revisit it then.
        """
        if email and email.strip().lower() in self._bootstrap_admins:
            return Role.ADMIN
        return Role.EVALUATOR
