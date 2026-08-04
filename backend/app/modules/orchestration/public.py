"""Public surface of Evaluation Orchestration (ARCHITECTURE.md §3).

Evaluation resolves `assignmentId → (content, instrumentVersion)` through here — a read-only sync
query, which 05-connect.md rule 2 allows. It never issues a command into this module: the
assignment becomes `submitted` because the completion policy hears `EvaluationSubmitted`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.orchestration.application import queries as _queries
from app.modules.orchestration.application.dtos import (
    AssignmentDTO,
    CampaignProgressDTO,
    ContentProgressDTO,
)
from app.modules.orchestration.infrastructure.repository import (
    SqlAlchemyAssignmentRepository,
    SqlAlchemyCampaignRepository,
)
from app.platform.uow import UnitOfWork, get_uow

# Events this module publishes.
CAMPAIGN_OPENED = "CampaignOpened"
CAMPAIGN_CLOSED = "CampaignClosed"
ASSIGNMENT_CREATED = "AssignmentCreated"
ASSIGNMENT_OPENED = "AssignmentOpened"
ASSIGNMENT_CANCELLED = "AssignmentCancelled"
CONTENT_EVALUATION_COMPLETED = "ContentEvaluationCompleted"

__all__ = [
    "ASSIGNMENT_CANCELLED",
    "ASSIGNMENT_CREATED",
    "ASSIGNMENT_OPENED",
    "CAMPAIGN_CLOSED",
    "CAMPAIGN_OPENED",
    "CONTENT_EVALUATION_COMPLETED",
    "AssignmentDTO",
    "CampaignProgressDTO",
    "ContentProgressDTO",
    "OrchestrationQueries",
    "get_orchestration_queries",
]


class OrchestrationQueries:
    """Read-only contract of Orchestration (`getPendingAssignments`, `getCampaignProgress`)."""

    def __init__(self, session: Session) -> None:
        self._assignments = SqlAlchemyAssignmentRepository(session)
        self._campaigns = SqlAlchemyCampaignRepository(session)

    def get_assignment(self, assignment_id: UUID) -> AssignmentDTO | None:
        return _queries.get_assignment(self._assignments, self._campaigns, assignment_id)

    def get_pending_assignments(self, assessor_id: UUID) -> list[AssignmentDTO]:
        return _queries.get_pending_assignments(self._assignments, self._campaigns, assessor_id)

    def get_campaign_progress(self, campaign_id: UUID) -> CampaignProgressDTO | None:
        return _queries.get_campaign_progress(self._assignments, self._campaigns, campaign_id)

    def list_assignments(self) -> list[AssignmentDTO]:
        """Every assignment across campaigns — input of the cross-campaign admin report."""
        return _queries.list_assignments(self._assignments, self._campaigns)


def get_orchestration_queries(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> OrchestrationQueries:
    return OrchestrationQueries(uow.session)
