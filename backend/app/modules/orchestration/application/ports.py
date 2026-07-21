"""Ports required by Orchestration's use cases. Implemented in infrastructure."""

from typing import Protocol
from uuid import UUID

from app.modules.orchestration.domain.assignment import Assignment
from app.modules.orchestration.domain.campaign import EvaluationCampaign


class CampaignRepositoryPort(Protocol):
    def get(self, campaign_id: UUID) -> EvaluationCampaign | None: ...

    def add(self, campaign: EvaluationCampaign) -> None: ...

    def update_status(self, campaign: EvaluationCampaign) -> None: ...

    def list_all(self) -> list[EvaluationCampaign]: ...


class AssignmentRepositoryPort(Protocol):
    def get(self, assignment_id: UUID) -> Assignment | None: ...

    def add(self, assignment: Assignment) -> None: ...

    def save_status(self, assignment: Assignment) -> None: ...

    def list_pending_for_assessor(self, assessor_id: UUID) -> list[Assignment]: ...

    def list_for_campaign(self, campaign_id: UUID) -> list[Assignment]: ...

    def find_active(
        self, campaign_id: UUID, content_id: UUID, assessor_id: UUID
    ) -> Assignment | None: ...

    def list_open_for_assessor_and_content(
        self, assessor_id: UUID, content_id: UUID
    ) -> list[Assignment]: ...

    def count_submitted(self, campaign_id: UUID, content_id: UUID) -> int: ...


class CompletionRepositoryPort(Protocol):
    def record_completion(
        self, campaign_id: UUID, content_id: UUID, rubric_version_id: str
    ) -> bool:
        """Insert the completion. Returns False if it was already recorded (idempotency)."""
        ...
