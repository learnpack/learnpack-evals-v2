"""Domain events published by Identity & Access (ADR-0049).

Identity published nothing until invitations existed, and that was consistent: the only
write path was a login upsert, which is not a fact about the roster but about a session.
Inviting somebody *is* a fact about the roster, and it is the one an audit reads — who was
asked in, by whom, with which role, and whether anybody ever used it.
"""

from app.modules.identity.domain.invitation import Invitation
from app.shared.domain.events import DomainEvent

INVITATION_AGGREGATE = "Invitation"


def _invitation_event(event_type: str, invitation: Invitation, **extra: object) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_type=INVITATION_AGGREGATE,
        aggregate_id=str(invitation.id),
        payload={
            "invitationId": str(invitation.id),
            "email": invitation.email,
            "role": str(invitation.role),
            "invitedBy": str(invitation.invited_by) if invitation.invited_by else None,
            "expiresAt": invitation.expires_at.isoformat() if invitation.expires_at else None,
            **extra,
        },
    )


def assessor_invited(invitation: Invitation) -> DomainEvent:
    return _invitation_event("AssessorInvited", invitation)


def invitation_resent(invitation: Invitation) -> DomainEvent:
    return _invitation_event("InvitationResent", invitation)


def invitation_revoked(invitation: Invitation) -> DomainEvent:
    return _invitation_event("InvitationRevoked", invitation)


def invitation_accepted(invitation: Invitation) -> DomainEvent:
    """The login that consumed it. `assessorId` is what the invitation produced — the
    single place where the roster's intent and a real credential meet."""
    return _invitation_event(
        "InvitationAccepted",
        invitation,
        assessorId=str(invitation.accepted_by) if invitation.accepted_by else None,
    )
