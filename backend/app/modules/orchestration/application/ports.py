"""Ports required by Orchestration's use cases. Implemented in infrastructure."""

from typing import Protocol
from uuid import UUID

from app.modules.orchestration.domain.assignment import Assignment
from app.modules.orchestration.domain.campaign import EvaluationCampaign


class CampaignRepositoryPort(Protocol):
    def get(self, campaign_id: UUID) -> EvaluationCampaign | None: ...

    def add(self, campaign: EvaluationCampaign) -> None: ...

    def update_status(self, campaign: EvaluationCampaign) -> None: ...

    def update_label(self, campaign: EvaluationCampaign) -> None:
        """Persist the name and the description — the pair a rename replaces (ADR-0055)."""
        ...

    def list_all(self) -> list[EvaluationCampaign]: ...


class DatasetsGatewayPort(Protocol):
    """The courses a dataset version holds (ADR-0058 §5).

    Declared in terms of ids alone, so the application layer keeps knowing nothing about the
    module on the other side of it (ARCHITECTURE.md §3). `None` means the store cannot resolve
    that version — which is not the same as a version that holds nothing, an impossibility the
    dataset's own invariants already refuse.
    """

    def get_version_members(self, version_id: UUID) -> list[UUID] | None: ...


class AssignmentRepositoryPort(Protocol):
    def get(self, assignment_id: UUID) -> Assignment | None: ...

    def add(self, assignment: Assignment) -> None: ...

    def save_status(self, assignment: Assignment) -> None: ...

    def list_pending_for_assessor(self, assessor_id: UUID) -> list[Assignment]: ...

    def list_for_campaign(self, campaign_id: UUID) -> list[Assignment]: ...

    def find_active(
        self, campaign_id: UUID, content_id: UUID, assessor_id: UUID
    ) -> Assignment | None: ...

    def count_submitted(self, campaign_id: UUID, content_id: UUID) -> int: ...

    def count_submitted_by_content(self, campaign_id: UUID) -> dict[UUID, int]:
        """The same count as `count_submitted`, for every content of the campaign at once.

        Asking per content is one query per course in scope, which a demo campaign never felt
        and forty courses do. A content with no submission is simply absent from the mapping;
        the caller iterates the campaign's scope, not this.
        """
        ...


class CompletionRepositoryPort(Protocol):
    def record_completion(
        self, campaign_id: UUID, content_id: UUID, instrument_version_id: str
    ) -> bool:
        """Insert the completion. Returns False if it was already recorded (idempotency)."""
        ...
