"""`EvaluationCampaign` — open, incremental aggregate (ADR-0002). Pure Python.

Config + scope of a human evaluation effort. It deliberately does **not** own its assignments
transactionally: a campaign opens with whatever assessors exist and gains more over time.

`requiredEvaluationsPerContent` is a **completion threshold, not provisioning**: a content is
complete when enough distinct assessors have *submitted*, regardless of how many assignments
were handed out or cancelled.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class InvalidCampaign(Exception):
    """The campaign breaks an invariant of its aggregate."""


@dataclass
class EvaluationCampaign:
    id: UUID
    name: str
    instrument_version_id: str
    required_evaluations_per_content: int
    # Optional, and never derived from the name: an absent description is absent (ADR-0055).
    description: str | None = None
    content_ids: list[UUID] = field(default_factory=list)
    golden_coverage_threshold: float = 1.0
    status: CampaignStatus = CampaignStatus.DRAFT

    def __post_init__(self) -> None:
        if not isinstance(self.status, CampaignStatus):
            self.status = CampaignStatus(self.status)
        if not self.name.strip():
            raise InvalidCampaign("name is required")
        if not self.instrument_version_id:
            raise InvalidCampaign("instrument_version_id is required")
        if self.required_evaluations_per_content < 1:
            raise InvalidCampaign("required_evaluations_per_content must be at least 1")
        if not 0 < self.golden_coverage_threshold <= 1:
            raise InvalidCampaign("golden_coverage_threshold must be within (0, 1]")

    def rename(self, name: str, description: str | None) -> None:
        """The label is replaced whole, in any status — it binds nothing (ADR-0055).

        Through `__post_init__` so the blank name is refused here by the same rule that
        refuses it on the way in: the aggregate owns it and there is no second copy.
        """
        self.name = name
        self.description = description
        self.__post_init__()

    def open(self) -> None:
        """Opening needs a non-empty scope — but NOT all the assignments (ADR-0002)."""
        if self.status is CampaignStatus.CLOSED:
            raise InvalidCampaign("a closed campaign cannot be reopened")
        if not self.content_ids:
            raise InvalidCampaign("cannot open a campaign with an empty content set")
        self.status = CampaignStatus.OPEN

    def close(self) -> None:
        if self.status is not CampaignStatus.OPEN:
            raise InvalidCampaign("only an open campaign can be closed")
        self.status = CampaignStatus.CLOSED

    def ensure_accepts_assignments(self) -> None:
        if self.status is not CampaignStatus.OPEN:
            raise InvalidCampaign(f"campaign is '{self.status}', not open")

    def includes(self, content_id: UUID) -> bool:
        return content_id in self.content_ids

    def is_complete_with(self, submitted_count: int) -> bool:
        """The quorum rule: distinct assessors who submitted reach the threshold."""
        return submitted_count >= self.required_evaluations_per_content
