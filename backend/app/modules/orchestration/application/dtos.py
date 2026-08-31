"""Orchestration's Published Language.

`AssignmentDTO` is what Evaluation reads to resolve `assignmentId → (content, instrumentVersion)`
— a read-only sync query across modules, which 05-connect.md rule 2 allows.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AssignmentDTO:
    assignment_id: UUID
    campaign_id: UUID
    content_id: UUID
    assessor_id: UUID
    status: str
    instrument_version_id: str

    @property
    def is_submitted(self) -> bool:
        return self.status == "submitted"

    @property
    def is_cancelled(self) -> bool:
        return self.status == "cancelled"


@dataclass(frozen=True)
class CampaignSummaryDTO:
    """What a campaign *is*, for a consumer that has to name it (ADR-0060 §1).

    A sibling of `CampaignProgressDTO`, not an extension of it. That one is Orchestration's
    published language towards Golden Dataset, and ADR-0055 §6 keeps the label out of it
    because a label is not progress. A report has the opposite need: it must say which round
    produced the numbers on the screen.
    """

    campaign_id: UUID
    name: str
    description: str | None
    status: str
    instrument_version_id: str
    required_evaluations_per_content: int
    # Null on campaigns opened before ADR-0058 — their scope was typed into a form.
    dataset_version_id: UUID | None
    content_ids: list[UUID]


@dataclass(frozen=True)
class ContentProgressDTO:
    content_id: UUID
    submitted_count: int
    required: int
    completed: bool


@dataclass(frozen=True)
class CampaignProgressDTO:
    campaign_id: UUID
    instrument_version_id: str
    status: str
    required_evaluations_per_content: int
    contents: list[ContentProgressDTO]
    # Campaign config; Golden Dataset reads it from here rather than from `campaigns`.
    golden_coverage_threshold: float = 1.0

    @property
    def completed_contents(self) -> int:
        return sum(1 for c in self.contents if c.completed)

    @property
    def coverage(self) -> float:
        """Share of the scope that reached quorum — what Golden Dataset consumes."""
        if not self.contents:
            return 0.0
        return self.completed_contents / len(self.contents)
