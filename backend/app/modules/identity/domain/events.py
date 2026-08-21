"""Domain events published by Identity & Access (ADR-0049).

Identity published nothing until invitations existed, and that was consistent: the only
write path was a login upsert, which is not a fact about the roster but about a session.
Inviting somebody *is* a fact about the roster, and it is the one an audit reads — who was
asked in, by whom, with which role, and whether anybody ever used it. Granting a role is the
same kind of fact, and the same audit reads both.
"""

from uuid import UUID

from app.modules.identity.domain.assessor import Assessor, Role
from app.modules.identity.domain.invitation import Invitation
from app.shared.domain.events import DomainEvent

INVITATION_AGGREGATE = "Invitation"
ASSESSOR_AGGREGATE = "Assessor"


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


def assessor_role_changed(assessor: Assessor, was: Role, changed_by: UUID) -> DomainEvent:
    """Who was granted what, by whom (ADR-0050).

    `from` is carried because the audit question is never "what is their role" — the
    assessors table answers that — but "what changed, and who decided it".
    """
    return DomainEvent(
        event_type="AssessorRoleChanged",
        aggregate_type=ASSESSOR_AGGREGATE,
        aggregate_id=str(assessor.id),
        payload={
            "assessorId": str(assessor.id),
            "from": str(was),
            "to": str(assessor.role),
            "changedBy": str(changed_by),
        },
    )


def _lifecycle_event(event_type: str, assessor: Assessor, changed_by: UUID) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_type=ASSESSOR_AGGREGATE,
        aggregate_id=str(assessor.id),
        payload={"assessorId": str(assessor.id), "changedBy": str(changed_by)},
    )


def assessor_expertise_changed(assessor: Assessor, changed_by: UUID) -> DomainEvent:
    """Somebody restated what this SME brings.

    The new value is carried and the old one is not: unlike a role, an expertise profile is
    a description rather than a grant, so what an audit asks is "who says this, and since
    when" — and the previous sentence is in the previous event.
    """
    return DomainEvent(
        event_type="AssessorExpertiseChanged",
        aggregate_type=ASSESSOR_AGGREGATE,
        aggregate_id=str(assessor.id),
        payload={
            "assessorId": str(assessor.id),
            "expertise": assessor.expertise,
            "changedBy": str(changed_by),
        },
    )


def assessor_deactivated(assessor: Assessor, changed_by: UUID) -> DomainEvent:
    """They stop taking part (ADR-0051). Nothing they produced is affected — this says the
    roster changed, not that the record did."""
    return _lifecycle_event("AssessorDeactivated", assessor, changed_by)


def assessor_reactivated(assessor: Assessor, changed_by: UUID) -> DomainEvent:
    return _lifecycle_event("AssessorReactivated", assessor, changed_by)


def invitation_accepted(invitation: Invitation) -> DomainEvent:
    """The login that consumed it. `assessorId` is what the invitation produced — the
    single place where the roster's intent and a real credential meet."""
    return _invitation_event(
        "InvitationAccepted",
        invitation,
        assessorId=str(invitation.accepted_by) if invitation.accepted_by else None,
    )
