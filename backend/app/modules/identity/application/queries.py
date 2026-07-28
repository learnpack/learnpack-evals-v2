"""Read-only query port of identity — how other modules look up an assessor.

Sync read-only queries across modules are allowed; writes are not (05-connect.md rule 2).
"""

from uuid import UUID

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.ports import AssessorRepositoryPort


def _to_dto(assessor) -> AssessorDTO:  # noqa: ANN001 — domain entity
    return AssessorDTO(
        assessor_id=assessor.id,
        role=str(assessor.role),
        email=assessor.email,
        display_name=assessor.display_name,
    )


def get_assessor(assessors: AssessorRepositoryPort, assessor_id: UUID) -> AssessorDTO | None:
    assessor = assessors.get_by_id(assessor_id)
    return None if assessor is None else _to_dto(assessor)


def list_assessors(
    assessors: AssessorRepositoryPort, assessor_ids: list[UUID]
) -> dict[UUID, AssessorDTO]:
    """Batch lookup, keyed by id — how reports put a name on an `assessorId`."""
    if not assessor_ids:
        return {}
    return {a.id: _to_dto(a) for a in assessors.list_by_ids(assessor_ids)}


def list_all_assessors(assessors: AssessorRepositoryPort) -> list[AssessorDTO]:
    """Every assessor — the admin console's assign picker (08-code.md §7)."""
    return [_to_dto(a) for a in assessors.list_all()]
