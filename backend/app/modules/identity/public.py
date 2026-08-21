"""Public surface of Identity (ARCHITECTURE.md §3).

Identity is generic and consumed by query: other modules only ever hold an `assessorId` and
resolve it to an `AssessorDTO` through here (Open Host Service, 05-connect.md).
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.identity.application import queries as _queries
from app.modules.identity.application.dtos import AssessorDTO, InvitationDTO
from app.modules.identity.infrastructure.invitation_repository import (
    SqlAlchemyInvitationRepository,
)
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.uow import UnitOfWork, get_uow

__all__ = ["AssessorDTO", "IdentityQueries", "InvitationDTO", "get_identity_queries"]


class IdentityQueries:
    """Read-only contract of Identity."""

    def __init__(self, session: Session) -> None:
        self._assessors = SqlAlchemyAssessorRepository(session)
        self._invitations = SqlAlchemyInvitationRepository(session)

    def get_assessor(self, assessor_id: UUID) -> AssessorDTO | None:
        return _queries.get_assessor(self._assessors, assessor_id)

    def list_assessors(self, assessor_ids: list[UUID]) -> dict[UUID, AssessorDTO]:
        """Batch lookup keyed by id (ADR-0006)."""
        return _queries.list_assessors(self._assessors, assessor_ids)

    def list_all_assessors(self) -> list[AssessorDTO]:
        """Every assessor — the admin console's assign picker."""
        return _queries.list_all_assessors(self._assessors)

    def list_invitations(self) -> list[InvitationDTO]:
        """Every invitation, newest first (ADR-0049)."""
        return _queries.list_invitations(self._invitations)

    def list_pending_invitations(self) -> list[InvitationDTO]:
        """The ones still waiting for a login — who the roster is expecting."""
        return _queries.list_pending_invitations(self._invitations)


def get_identity_queries(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> IdentityQueries:
    return IdentityQueries(uow.session)
