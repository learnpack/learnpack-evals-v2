"""The cross-campaign workload report — Reporting's read side (CQRS query side).

Composes the other modules through their **public query surfaces** and aggregates in Python
(ADR-0006): no cross-module JOINs, no read-model tables. Reads are batched, so the cost is
two or three queries regardless of how many courses there are.

**Who evaluated what is the only question this file still answers across campaigns.** It is a
question about people — who is overloaded, who abandoned, who has not opened anything — and 25
experts over several rounds is exactly when it needs asking without a campaign in the way.
*What a course scored* is not that kind of question: it is a measurement, and it has no answer
outside the campaign that fixed the instrument, the scope and the panel. That report lives in
`campaign_report.py` (ADR-0060 §6).

This lives in `infrastructure` on purpose: consuming another module's published contract is
an outbound concern, which keeps `reporting/application` (the pure aggregation) free of any
dependency on other modules. The builder takes its collaborators as parameters, so it stays
unit-testable with fakes.
"""

from dataclasses import dataclass
from uuid import UUID

from app.modules.evaluand_registry.public import EvaluandRegistryQueries
from app.modules.identity.public import IdentityQueries
from app.modules.orchestration.public import OrchestrationQueries


def _name_of(names: dict, assessor_id: UUID) -> str | None:
    dto = names.get(assessor_id)
    return None if dto is None else (dto.display_name or dto.email)


@dataclass(frozen=True)
class AssignmentCountsDTO:
    assigned: int = 0
    opened: int = 0
    submitted: int = 0
    cancelled: int = 0

    @property
    def pending(self) -> int:
        return self.assigned + self.opened


@dataclass(frozen=True)
class AssessorProgressDTO:
    assessor_id: UUID
    display_name: str | None
    counts: AssignmentCountsDTO


@dataclass(frozen=True)
class ContentProgressRowDTO:
    content_id: UUID
    external_id: str
    counts: AssignmentCountsDTO


@dataclass(frozen=True)
class ProgressReportDTO:
    by_assessor: list[AssessorProgressDTO]
    by_content: list[ContentProgressRowDTO]


def build_progress_report(
    orchestration: OrchestrationQueries,
    contents: EvaluandRegistryQueries,
    identity: IdentityQueries,
) -> ProgressReportDTO:
    """Who evaluated what, across campaigns (08-code.md §7).

    Complements `/admin/campaigns/{id}/progress`, which is the within-campaign quorum view.
    """
    assignments = orchestration.list_assignments()

    per_assessor: dict[UUID, dict[str, int]] = {}
    per_content: dict[UUID, dict[str, int]] = {}
    for assignment in assignments:
        per_assessor.setdefault(assignment.assessor_id, {})
        per_content.setdefault(assignment.content_id, {})
        per_assessor[assignment.assessor_id][assignment.status] = (
            per_assessor[assignment.assessor_id].get(assignment.status, 0) + 1
        )
        per_content[assignment.content_id][assignment.status] = (
            per_content[assignment.content_id].get(assignment.status, 0) + 1
        )

    names = identity.list_assessors(list(per_assessor))
    external_ids = {s.content_id: s.external_id for s in contents.list_content_snapshots()}

    return ProgressReportDTO(
        by_assessor=[
            AssessorProgressDTO(
                assessor_id=assessor_id,
                display_name=_name_of(names, assessor_id),
                counts=_counts(statuses),
            )
            for assessor_id, statuses in sorted(per_assessor.items(), key=lambda i: str(i[0]))
        ],
        by_content=[
            ContentProgressRowDTO(
                content_id=content_id,
                external_id=external_ids.get(content_id, ""),
                counts=_counts(statuses),
            )
            for content_id, statuses in sorted(per_content.items(), key=lambda i: str(i[0]))
        ],
    )


def _counts(statuses: dict[str, int]) -> AssignmentCountsDTO:
    return AssignmentCountsDTO(
        assigned=statuses.get("assigned", 0),
        opened=statuses.get("opened", 0),
        submitted=statuses.get("submitted", 0),
        cancelled=statuses.get("cancelled", 0),
    )
