"""Read-only query port of identity — how other modules look up an assessor.

Sync read-only queries across modules are allowed; writes are not (05-connect.md rule 2).
"""

from uuid import UUID

from app.modules.identity.application.dtos import AssessorDTO, AutomatedIdentity, InvitationDTO
from app.modules.identity.application.invitations import to_dto as invitation_to_dto
from app.modules.identity.application.ports import (
    AssessorRepositoryPort,
    InvitationRepositoryPort,
)


def to_dto(assessor) -> AssessorDTO:  # noqa: ANN001 — domain entity
    config = assessor.source_config or {}
    return AssessorDTO(
        assessor_id=assessor.id,
        role=str(assessor.role),
        email=assessor.email,
        display_name=assessor.display_name,
        kind=str(assessor.kind),
        status=str(assessor.status),
        expertise=assessor.expertise,
        # The aggregate guarantees the three keys for an automated assessor; a human has
        # no `source_config` at all.
        automated=(
            AutomatedIdentity(
                name=config["name"],
                version=config["version"],
                instrument_id=config["instrumentId"],
            )
            if str(assessor.kind) == "automated"
            else None
        ),
    )


def get_assessor(assessors: AssessorRepositoryPort, assessor_id: UUID) -> AssessorDTO | None:
    assessor = assessors.get_by_id(assessor_id)
    return None if assessor is None else to_dto(assessor)


def list_assessors(
    assessors: AssessorRepositoryPort, assessor_ids: list[UUID]
) -> dict[UUID, AssessorDTO]:
    """Batch lookup, keyed by id — how reports put a name on an `assessorId`."""
    if not assessor_ids:
        return {}
    return {a.id: to_dto(a) for a in assessors.list_by_ids(assessor_ids)}


def list_all_assessors(assessors: AssessorRepositoryPort) -> list[AssessorDTO]:
    """Every assessor — the admin console's assign picker (08-code.md §7)."""
    return [to_dto(a) for a in assessors.list_all()]


def list_invitations(invitations: InvitationRepositoryPort) -> list[InvitationDTO]:
    """Every invitation, newest first — the console's roster of acts (ADR-0049)."""
    return [invitation_to_dto(i) for i in invitations.list_all()]


def list_pending_invitations(invitations: InvitationRepositoryPort) -> list[InvitationDTO]:
    """Only the ones still waiting for a login. Expired ones are included: expiry is
    derived, so an expired invitation is a pending one whose window closed."""
    return [invitation_to_dto(i) for i in invitations.list_pending()]
