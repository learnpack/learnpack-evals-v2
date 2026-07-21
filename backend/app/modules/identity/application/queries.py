"""Read-only query port of identity — how other modules look up an assessor.

Sync read-only queries across modules are allowed; writes are not (05-connect.md rule 2).
"""

from uuid import UUID

from app.modules.identity.application.dtos import AssessorDTO
from app.modules.identity.application.ports import AssessorRepositoryPort


def get_assessor(assessors: AssessorRepositoryPort, assessor_id: UUID) -> AssessorDTO | None:
    assessor = assessors.get_by_id(assessor_id)
    if assessor is None:
        return None
    return AssessorDTO(
        assessor_id=assessor.id,
        role=str(assessor.role),
        email=assessor.email,
        display_name=assessor.display_name,
    )
