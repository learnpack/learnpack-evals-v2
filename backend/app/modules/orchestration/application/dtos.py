"""Orchestration's Published Language.

`AssignmentDTO` is what Evaluation reads to resolve `assignmentId → (content, rubricVersion)`
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
    rubric_version_id: str
    metadata_view: list[str]

    @property
    def is_submitted(self) -> bool:
        return self.status == "submitted"

    @property
    def is_cancelled(self) -> bool:
        return self.status == "cancelled"


@dataclass(frozen=True)
class ContentProgressDTO:
    content_id: UUID
    submitted_count: int
    required: int
    completed: bool


@dataclass(frozen=True)
class CampaignProgressDTO:
    campaign_id: UUID
    rubric_version_id: str
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
