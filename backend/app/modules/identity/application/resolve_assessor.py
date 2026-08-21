"""Resolve a verified Clerk identity into our own `Assessor` (ADR-0004).

Entry point of every authenticated request: on first login the assessor is created; later
logins only refresh the profile. The role is deliberately never touched here — promotion is
an admin act, so a login can never escalate privileges.

**First login is also where an invitation is redeemed** (ADR-0049). That is not an exception
to the sentence above: an invitation is consumed exactly once, at the moment the assessor is
created, and it cannot reach an assessor that already exists. What it grants was decided by
an admin before the person ever arrived — the login carries no say in it.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.ports import (
    AssessorRepositoryPort,
    InvitationRepositoryPort,
)
from app.modules.identity.domain import events
from app.modules.identity.domain.assessor import Assessor, Role
from app.modules.identity.domain.invitation import Invitation
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClerkIdentity:
    """The claims we care about, already verified by the Clerk adapter.

    `email_verified` is the provider's statement that this session's owner controls that
    address — not our own. It gates redemption and nothing else, because matching an
    invitation on an unverified address is how somebody else's invitation gets accepted
    (the *false identifier* anti-pattern; it has produced real CVEs).
    """

    clerk_user_id: str
    email: str | None = None
    display_name: str | None = None
    email_verified: bool = False


class ResolveAssessor:
    def __init__(
        self,
        assessors: AssessorRepositoryPort,
        invitations: InvitationRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
        bootstrap_admins: Iterable[str] = (),
    ) -> None:
        self._assessors = assessors
        self._invitations = invitations
        self._publisher = publisher
        self._uow = uow
        # Provisioning allowlist, NOT an authorisation source — see `_initial_role`.
        self._bootstrap_admins = frozenset(e.strip().lower() for e in bootstrap_admins if e)

    def __call__(self, identity: ClerkIdentity) -> AssessorDTO:
        assessor = self._assessors.get_by_clerk_user_id(identity.clerk_user_id)

        if assessor is None:
            invitation = self._redeemable_invitation(identity)
            assessor = Assessor(
                id=new_id(),
                clerk_user_id=identity.clerk_user_id,
                email=identity.email,
                # The provider's name if it sent one, otherwise the one the admin typed when
                # inviting: the roster knew who it was expecting.
                display_name=identity.display_name
                or (invitation.display_name if invitation else None),
                role=self._granted_role(identity, invitation),
                # The expertise profile a human assessor carries (GLOSSARY). Until
                # invitations existed, nothing ever wrote it.
                expertise=invitation.expertise if invitation else None,
            )
            self._assessors.add(assessor)

            if invitation is not None:
                invitation.redeem(assessor.id)
                self._invitations.update(invitation)
                self._publisher.publish(events.invitation_accepted(invitation))

            self._uow.commit()
        elif assessor.update_profile(identity.email, identity.display_name):
            # Note what is *not* here: the role, and no invitation lookup either. An
            # existing assessor's role never changes on login, whatever the allowlist or a
            # stray invitation says — logging in cannot escalate privileges.
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

    def _redeemable_invitation(self, identity: ClerkIdentity) -> Invitation | None:
        """The invitation this brand-new assessor is answering, if there is one.

        Requires a **verified** address. When the claim is missing the provider's JWT
        template is not sending it, and the failure mode that matters is the silent one:
        every invitation would sit pending forever while people signed in and got the
        default role. So the miss is logged loudly, naming the remedy, instead of being
        swallowed as "no invitation".
        """
        if not identity.email:
            return None

        invitation = self._invitations.find_pending_by_email(identity.email)
        if invitation is None:
            return None

        if not identity.email_verified:
            logger.warning(
                "not redeeming the invitation for %s: the identity claims carry no verified "
                "email. Add `email_verified` to the provider's JWT template - until then "
                "invitations stay pending and new assessors get the default role (ADR-0049).",
                identity.email,
            )
            return None

        return invitation if invitation.is_redeemable() else None

    def _granted_role(self, identity: ClerkIdentity, invitation: Invitation | None) -> Role:
        """The role a brand-new assessor is created with.

        An invitation wins over the allowlist: it is a deliberate act, taken per person and
        recorded with its author, while `ADMIN_EMAILS` is a creation default for whoever
        arrives without one. Both apply **at creation and never again**, so `assessors.role`
        stays the single source of truth.
        """
        if invitation is not None:
            return invitation.role
        return self._initial_role(identity.email)

    def _initial_role(self, email: str | None) -> Role:
        """The default when nobody was invited.

        The allowlist solves bootstrapping only: someone has to be able to register content
        and open a campaign before any admin exists to invite anyone. It applies **at
        creation and never again**, so it behaves like a default, not like a permission.

        Safe because access is invite-only (ADR-0004): an attacker cannot sign up with an
        admin's address, they would need the invitation. If invite-only were ever turned
        off, this would become an escalation path — revisit it then.
        """
        if email and email.strip().lower() in self._bootstrap_admins:
            return Role.ADMIN
        return Role.EVALUATOR
