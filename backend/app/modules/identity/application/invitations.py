"""Use cases over `Invitation` — registering a human evaluator (ADR-0049).

Each writes its aggregate and publishes its event through the same unit of work, so the
outbox row commits atomically with the state change (ADR-0003). The dispatcher is called
**after** the commit: announcing an invitation that then rolled back would be the one lie
this surface must not tell.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.modules.identity.application.dtos import InvitationDTO
from app.modules.identity.application.ports import (
    AssessorRepositoryPort,
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


class InvitationNotFound(Exception): ...


class AssessorAlreadyRegistered(Exception):
    """That address already signed in once — there is nothing left to invite."""


class InvitationAlreadyPending(Exception):
    """An invitation for that address is already waiting; re-send it instead of stacking
    a second one, which would make two roles compete for the same first login."""


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

    def __call__(self, command: InviteAssessorCommand) -> InvitationDTO:
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

        self._dispatcher.dispatch(invitation)
        return to_dto(invitation)


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
    ) -> InvitationDTO:
        invitation = self._invitations.get(invitation_id)
        if invitation is None:
            raise InvitationNotFound(str(invitation_id))

        invitation.extend(validity)
        self._invitations.update(invitation)
        self._publisher.publish(events.invitation_resent(invitation))
        self._uow.commit()

        self._dispatcher.dispatch(invitation)
        return to_dto(invitation)


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
