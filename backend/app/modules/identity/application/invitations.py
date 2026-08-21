"""Use cases over `Invitation` — registering a human evaluator (ADR-0049).

Each writes its aggregate and publishes its event through the same unit of work, so the
outbox row commits atomically with the state change (ADR-0003). The dispatcher is called
**after** the commit: announcing an invitation that then rolled back would be the one lie
this surface must not tell.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.modules.identity.application.dtos import InvitationDTO
from app.modules.identity.application.ports import (
    AssessorRepositoryPort,
    InvitationDeliveryFailed,
    InvitationDispatcherPort,
    InvitationRepositoryPort,
)
from app.modules.identity.domain import events
from app.modules.identity.domain.assessor import Role
from app.modules.identity.domain.invitation import (
    DEFAULT_VALIDITY,
    Invitation,
    normalize_email,
)
from app.shared.application.ports import EventPublisherPort, UnitOfWorkPort
from app.shared.domain.ids import new_id

logger = logging.getLogger(__name__)


class InvitationNotFound(Exception): ...


class AssessorAlreadyRegistered(Exception):
    """That address already signed in once — there is nothing left to invite."""


class InvitationAlreadyPending(Exception):
    """An invitation for that address is already waiting; re-send it instead of stacking
    a second one, which would make two roles compete for the same first login."""


@dataclass(frozen=True)
class InvitationSent:
    """What an act that delivers returns: the invitation, and whether it got out.

    Two separate facts, and they can disagree. The invitation is committed before delivery
    is attempted, so a provider that is down or that refuses the address leaves a perfectly
    valid pending row nobody was told about — which looks exactly like one somebody is
    ignoring unless the answer says otherwise.
    """

    invitation: InvitationDTO
    delivered: bool
    delivery_error: str | None = None


def to_dto(invitation: Invitation, now: datetime | None = None) -> InvitationDTO:
    return InvitationDTO(
        invitation_id=invitation.id,
        email=invitation.email,
        role=str(invitation.role),
        display_name=invitation.display_name,
        expertise=invitation.expertise,
        invited_by=invitation.invited_by,
        status=str(invitation.status),
        expires_at=invitation.expires_at,
        # Derived here rather than stored, so a reader can never see `pending` next to a
        # date that has passed (ADR-0049).
        expired=invitation.is_expired(now),
        accepted_by=invitation.accepted_by,
        created_at=invitation.created_at,
    )


@dataclass(frozen=True)
class InviteAssessorCommand:
    email: str
    role: Role = Role.EVALUATOR
    display_name: str | None = None
    expertise: str | None = None
    invited_by: UUID | None = None
    validity: timedelta = DEFAULT_VALIDITY


class InviteAssessor:
    """The act that registers a human evaluator. It creates no account: what it creates is
    the pending fact a first login consumes (ADR-0049)."""

    def __init__(
        self,
        invitations: InvitationRepositoryPort,
        assessors: AssessorRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
        dispatcher: InvitationDispatcherPort,
    ) -> None:
        self._invitations = invitations
        self._assessors = assessors
        self._publisher = publisher
        self._uow = uow
        self._dispatcher = dispatcher

    def __call__(self, command: InviteAssessorCommand) -> InvitationSent:
        email = normalize_email(command.email)

        if self._assessors.get_by_email(email) is not None:
            raise AssessorAlreadyRegistered(email)
        # The partial unique index is the backstop; this is what gives a clean 409 naming
        # the remedy.
        if self._invitations.find_pending_by_email(email) is not None:
            raise InvitationAlreadyPending(email)

        invitation = Invitation(
            id=new_id(),
            email=email,
            role=command.role,
            display_name=command.display_name,
            expertise=command.expertise,
            invited_by=command.invited_by,
            expires_at=datetime.now(UTC) + command.validity,
        )
        self._invitations.add(invitation)
        self._publisher.publish(events.assessor_invited(invitation))
        self._uow.commit()

        return _deliver(self._dispatcher, invitation)


class ResendInvitation:
    """Give a pending invitation a fresh window. An expired one is still pending, so this
    is exactly the remedy for a window that closed before anybody signed in."""

    def __init__(
        self,
        invitations: InvitationRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
        dispatcher: InvitationDispatcherPort,
    ) -> None:
        self._invitations = invitations
        self._publisher = publisher
        self._uow = uow
        self._dispatcher = dispatcher

    def __call__(
        self, invitation_id: UUID, validity: timedelta = DEFAULT_VALIDITY
    ) -> InvitationSent:
        invitation = self._invitations.get(invitation_id)
        if invitation is None:
            raise InvitationNotFound(str(invitation_id))

        invitation.extend(validity)
        self._invitations.update(invitation)
        self._publisher.publish(events.invitation_resent(invitation))
        self._uow.commit()

        return _deliver(self._dispatcher, invitation)


class RevokeInvitation:
    """Withdraw an invitation nobody used. It leaves the address free to be invited again —
    which is why the uniqueness index only covers pending rows."""

    def __init__(
        self,
        invitations: InvitationRepositoryPort,
        publisher: EventPublisherPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self._invitations = invitations
        self._publisher = publisher
        self._uow = uow

    def __call__(self, invitation_id: UUID) -> InvitationDTO:
        invitation = self._invitations.get(invitation_id)
        if invitation is None:
            raise InvitationNotFound(str(invitation_id))

        invitation.revoke()
        self._invitations.update(invitation)
        self._publisher.publish(events.invitation_revoked(invitation))
        self._uow.commit()
        return to_dto(invitation)


def _deliver(dispatcher: InvitationDispatcherPort, invitation: Invitation) -> InvitationSent:
    """Attempt delivery after the commit, and never let its failure undo the act.

    The roster's record of who was asked in is true whether or not an email went out. What a
    failure changes is what the admin has to do next — re-send, or invite that person in the
    provider by hand — so it is reported rather than raised.
    """
    try:
        dispatcher.dispatch(invitation)
    except InvitationDeliveryFailed as exc:
        logger.warning("invitation for %s was not delivered: %s", invitation.email, exc)
        return InvitationSent(to_dto(invitation), delivered=False, delivery_error=str(exc))
    return InvitationSent(to_dto(invitation), delivered=True)
