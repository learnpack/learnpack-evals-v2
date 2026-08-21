"""HTTP adapter for Identity: the admin's roster of assessors and the invitations to it.

Reading the roster was the whole surface until invitations existed, because the only write
path into Identity was the login upsert (`ResolveAssessor`, ADR-0004) and role changes lived
in the CLI. Inviting is a write, and it belongs here: it is the act that registers a human
evaluator (ADR-0049), and it creates no account — the `assessors` row still appears at that
address's first login.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.identity.application.change_role import (
    CannotChangeOwnRole,
    CannotDemoteLastAdmin,
    ChangeAssessorRole,
    ChangeAssessorRoleCommand,
)
from app.modules.identity.application.deactivate_assessor import (
    CannotDeactivateLastAdmin,
    CannotDeactivateYourself,
    SetAssessorActive,
    SetAssessorActiveCommand,
)
from app.modules.identity.application.dtos import AssessorDTO, InvitationDTO
from app.modules.identity.application.errors import AssessorNotFound, NotAHumanAssessor
from app.modules.identity.application.invitations import (
    AssessorAlreadyRegistered,
    InvitationAlreadyPending,
    InvitationNotFound,
    InvitationSent,
    InviteAssessor,
    InviteAssessorCommand,
    ResendInvitation,
    RevokeInvitation,
)
from app.modules.identity.application.set_expertise import (
    SetAssessorExpertise,
    SetAssessorExpertiseCommand,
)
from app.modules.identity.domain.assessor import Role
from app.modules.identity.domain.invitation import InvalidInvitation, InvalidInvitationTransition
from app.modules.identity.infrastructure.dispatchers import get_invitation_dispatcher
from app.modules.identity.infrastructure.invitation_repository import (
    SqlAlchemyInvitationRepository,
)
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.modules.identity.public import IdentityQueries, get_identity_queries
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

admin_router = APIRouter(prefix="/admin", tags=["identity-admin"])

Identities = Annotated[IdentityQueries, Depends(get_identity_queries)]
Uow = Annotated[UnitOfWork, Depends(get_uow)]


class AutomatedIdentityResponse(BaseModel):
    """Present exactly when `kind == 'automated'` — the artifact and its lineage."""

    name: str
    version: str
    instrument_id: str


class AssessorResponse(BaseModel):
    assessor_id: UUID
    role: str
    email: str | None = None
    display_name: str | None = None
    kind: str = "human"
    # `active` or `deactivated` (ADR-0051). Published because a picker that silently drops
    # somebody reads as a bug; the caller decides how to show them.
    status: str = "active"
    # What the invitation declared and the redemption wrote (ADR-0049). Null for an
    # automated assessor, and for anybody who joined before invitations existed.
    expertise: str | None = None
    automated: AutomatedIdentityResponse | None = None


class InvitationResponse(BaseModel):
    invitation_id: UUID
    email: str
    role: str
    status: str
    # Derived from `expires_at`, never stored (ADR-0049): a pending row whose window closed
    # must not read as merely pending.
    expired: bool
    display_name: str | None = None
    expertise: str | None = None
    invited_by: UUID | None = None
    expires_at: datetime | None = None
    accepted_by: UUID | None = None
    created_at: datetime | None = None
    # Only the two acts that deliver answer these; a listing leaves them null, because
    # whether an email got out days ago is not a fact this row carries (ADR-0049 §8).
    delivered: bool | None = None
    delivery_error: str | None = None


class ChangeRoleRequest(BaseModel):
    role: str = Field(examples=["admin"])


class SetActiveRequest(BaseModel):
    active: bool


class SetExpertiseRequest(BaseModel):
    # Nullable and blank-tolerant: clearing a profile is a correction like any other, and the
    # aggregate treats an empty box and an unfilled one as the same thing.
    expertise: str | None = None


class InviteAssessorRequest(BaseModel):
    # A plain string, validated by the aggregate rather than by `EmailStr`: the shape of an
    # address is a rule of the invitation, and the domain already normalizes and refuses it
    # in the one place the CLI goes through too.
    email: str = Field(examples=["ada@example.com"])
    role: str = Field(default="evaluator", examples=["evaluator"])
    display_name: str | None = None
    expertise: str | None = Field(
        default=None,
        description="The expertise profile this SME brings, as the roster knows it.",
    )


def _to_response(invitation: InvitationDTO) -> InvitationResponse:
    return InvitationResponse(**vars(invitation))


def _sent_response(sent: InvitationSent) -> InvitationResponse:
    return _to_response(sent.invitation).model_copy(
        update={"delivered": sent.delivered, "delivery_error": sent.delivery_error}
    )


def _assessor_response(a: AssessorDTO) -> AssessorResponse:
    return AssessorResponse(
        assessor_id=a.assessor_id,
        role=a.role,
        email=a.email,
        display_name=a.display_name,
        kind=a.kind,
        status=a.status,
        expertise=a.expertise,
        automated=(
            AutomatedIdentityResponse(
                name=a.automated.name,
                version=a.automated.version,
                instrument_id=a.automated.instrument_id,
            )
            if a.automated is not None
            else None
        ),
    )


@admin_router.get("/assessors", response_model=list[AssessorResponse])
def list_assessors(admin: AdminAssessor, identities: Identities) -> list[AssessorResponse]:
    """Every assessor, of both kinds. The assign picker filters `role == 'evaluator'`
    client-side; the assessors page groups by `kind`, which is why it is stated here —
    the two kinds are structurally different (ADR-0016) and a list that mixes them
    without saying so cannot be read."""
    return [_assessor_response(a) for a in identities.list_all_assessors()]


@admin_router.patch("/assessors/{assessor_id}", response_model=AssessorResponse)
def change_assessor_role(
    assessor_id: UUID, request: ChangeRoleRequest, admin: AdminAssessor, uow: Uow
) -> AssessorResponse:
    """Grant or withdraw a role (ADR-0050).

    Not a login path: this is an admin-only act with an author in the outbox, so the
    invariant ADR-0007 protects — authenticating cannot escalate a privilege — is untouched.
    """
    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown role: {request.role!r}",
        ) from None

    use_case = ChangeAssessorRole(
        assessors=SqlAlchemyAssessorRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        assessor = use_case(
            ChangeAssessorRoleCommand(
                assessor_id=assessor_id, role=role, changed_by=admin.assessor_id
            )
        )
    except AssessorNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="assessor not found"
        ) from exc
    except CannotChangeOwnRole as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="you cannot change your own role - somebody else grants it",
        ) from exc
    except CannotDemoteLastAdmin as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="this is the last admin - promote somebody else first, or nobody could "
            "grant the role back",
        ) from exc
    except NotAHumanAssessor as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an automated assessor has no role - what it may do is decided by "
            "ratification (ADR-0019)",
        ) from exc
    return _assessor_response(assessor)


@admin_router.post("/assessors/{assessor_id}/active", response_model=AssessorResponse)
def set_assessor_active(
    assessor_id: UUID, request: SetActiveRequest, admin: AdminAssessor, uow: Uow
) -> AssessorResponse:
    """Withdraw an assessor from the future, or bring them back (ADR-0051).

    Not a deletion: everything they produced stays, because it records what happened. What
    changes is that they are offered no new work and no longer get through the door.
    """
    use_case = SetAssessorActive(
        assessors=SqlAlchemyAssessorRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        assessor = use_case(
            SetAssessorActiveCommand(
                assessor_id=assessor_id, active=request.active, changed_by=admin.assessor_id
            )
        )
    except AssessorNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="assessor not found"
        ) from exc
    except CannotDeactivateYourself as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="you cannot deactivate yourself - it would lock you out in one click",
        ) from exc
    except CannotDeactivateLastAdmin as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="this is the last admin - promote somebody else first, or nobody could "
            "bring them back",
        ) from exc
    except NotAHumanAssessor as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an automated assessor is withdrawn by ceasing to declare it in code, "
            "not from here",
        ) from exc
    return _assessor_response(assessor)


@admin_router.patch("/assessors/{assessor_id}/expertise", response_model=AssessorResponse)
def set_assessor_expertise(
    assessor_id: UUID, request: SetExpertiseRequest, admin: AdminAssessor, uow: Uow
) -> AssessorResponse:
    """Correct the expertise profile an invitation declared (ADR-0049).

    Its own endpoint rather than a second field on the role one: granting a role decides what
    somebody may do and carries the two refusals that go with that, while this decides
    nothing. Blank clears it.
    """
    use_case = SetAssessorExpertise(
        assessors=SqlAlchemyAssessorRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        assessor = use_case(
            SetAssessorExpertiseCommand(
                assessor_id=assessor_id,
                expertise=request.expertise,
                changed_by=admin.assessor_id,
            )
        )
    except AssessorNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="assessor not found"
        ) from exc
    except NotAHumanAssessor as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an automated assessor has no expertise profile - what it can judge is "
            "its declared coverage (ADR-0018)",
        ) from exc
    return _assessor_response(assessor)


# ------------------------------------------------------------------------- invitations


@admin_router.get("/invitations", response_model=list[InvitationResponse])
def list_invitations(admin: AdminAssessor, identities: Identities) -> list[InvitationResponse]:
    """Newest first, in every state. Accepted and revoked rows stay because the question
    the console answers is not only "who is waiting" but "what did we do"."""
    return [_to_response(i) for i in identities.list_invitations()]


@admin_router.post(
    "/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED
)
def invite_assessor(
    request: InviteAssessorRequest, admin: AdminAssessor, uow: Uow
) -> InvitationResponse:
    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown role: {request.role!r}",
        ) from None

    use_case = InviteAssessor(
        invitations=SqlAlchemyInvitationRepository(uow.session),
        assessors=SqlAlchemyAssessorRepository(uow.session),
        publisher=uow.events,
        uow=uow,
        dispatcher=get_invitation_dispatcher(),
    )
    try:
        sent = use_case(
            InviteAssessorCommand(
                email=str(request.email),
                role=role,
                display_name=request.display_name,
                expertise=request.expertise,
                invited_by=admin.assessor_id,
            )
        )
    except AssessorAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{exc} has already signed in - change their role instead of inviting them",
        ) from exc
    except InvitationAlreadyPending as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{exc} already has a pending invitation - re-send or revoke that one",
        ) from exc
    except InvalidInvitation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _sent_response(sent)


@admin_router.post("/invitations/{invitation_id}/resend", response_model=InvitationResponse)
def resend_invitation(invitation_id: UUID, admin: AdminAssessor, uow: Uow) -> InvitationResponse:
    """Give a pending invitation a fresh window — including one that already expired,
    which is still pending and is exactly what this remedies."""
    use_case = ResendInvitation(
        invitations=SqlAlchemyInvitationRepository(uow.session),
        publisher=uow.events,
        uow=uow,
        dispatcher=get_invitation_dispatcher(),
    )
    return _sent_response(_act(use_case, invitation_id))


@admin_router.post("/invitations/{invitation_id}/revoke", response_model=InvitationResponse)
def revoke_invitation(invitation_id: UUID, admin: AdminAssessor, uow: Uow) -> InvitationResponse:
    use_case = RevokeInvitation(
        invitations=SqlAlchemyInvitationRepository(uow.session), publisher=uow.events, uow=uow
    )
    return _to_response(_act(use_case, invitation_id))


def _act[T](use_case: Callable[[UUID], T], invitation_id: UUID) -> T:
    """The two refusals every act on one invitation shares: it does not exist, or it is no
    longer pending. Generic in what the act returns — re-sending reports delivery, revoking
    has nothing to deliver."""
    try:
        return use_case(invitation_id)
    except InvitationNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="invitation not found"
        ) from exc
    except InvalidInvitationTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
