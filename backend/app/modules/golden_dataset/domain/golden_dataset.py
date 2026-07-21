"""`GoldenDataset` — the curated human ground truth. Pure Python.

A `GoldenDataset` exists per `(contentSet, rubricVersion)`. In the MVP the content set is a
campaign's scope, so it is keyed by `(campaign, rubricVersion)` — the PK of
`golden_references`.

Its one rule (07-define.md): the reference becomes **usable** when coverage reaches the
threshold. Coverage is the share of the scope whose contents reached quorum — each included
content therefore already has its N human evaluations (`ContentEvaluationCompleted`).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class InvalidGoldenReference(Exception):
    """The reference breaks an invariant."""


def is_usable(coverage: float, threshold: float) -> bool:
    """The rule that makes a golden reference usable (`coverage >= threshold`)."""
    return coverage >= threshold


@dataclass(frozen=True)
class GoldenReference:
    """The established fact: this campaign's human ground truth is usable."""

    campaign_id: UUID
    rubric_version_id: str
    coverage: float
    established_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.rubric_version_id:
            raise InvalidGoldenReference("rubric_version_id is required")
        if not 0 <= self.coverage <= 1:
            raise InvalidGoldenReference("coverage must be within [0, 1]")
