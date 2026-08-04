"""Report builders — Reporting's read side (CQRS query side).

Composes the other modules through their **public query surfaces** and aggregates in Python
(ADR-0006): no cross-module JOINs, no read-model tables. Reads are batched, so the cost is
two or three queries per report regardless of how many courses there are.

This lives in `infrastructure` on purpose: consuming another module's published contract is
an outbound concern, which keeps `reporting/application` (the pure aggregation) free of any
dependency on other modules. The builders take their collaborators as parameters, so they
stay unit-testable with fakes.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.evaluand_registry.public import EvaluandRegistryQueries
from app.modules.evaluation.public import EvaluationDTO, EvaluationQueries
from app.modules.identity.public import IdentityQueries
from app.modules.orchestration.public import OrchestrationQueries
from app.modules.reporting.application import aggregation
from app.modules.reporting.application.aggregation import Dispersion


@dataclass(frozen=True)
class ScoreDetailDTO:
    criterion_id: str
    score: int
    comment: str | None


@dataclass(frozen=True)
class IndividualEvaluationDTO:
    evaluation_id: UUID
    assessor_id: UUID
    assessor_name: str | None
    submitted_at: datetime | None
    superseded: bool
    scores: list[ScoreDetailDTO]


@dataclass(frozen=True)
class CriterionSummaryDTO:
    criterion_id: str
    average: float
    dispersion: Dispersion


@dataclass(frozen=True)
class ContentScoresDTO:
    content_id: UUID
    external_id: str
    generating_system: str
    version: str
    average: float | None
    evaluator_count: int
    criteria: list[CriterionSummaryDTO]
    evaluations: list[IndividualEvaluationDTO]


@dataclass(frozen=True)
class AssessorAverageDTO:
    assessor_id: UUID
    display_name: str | None
    email: str | None
    evaluation_count: int
    average: float | None


@dataclass(frozen=True)
class ScoresReportDTO:
    contents: list[ContentScoresDTO]
    assessors: list[AssessorAverageDTO]
    global_average: float | None


def build_scores_report(
    contents: EvaluandRegistryQueries,
    evaluations: EvaluationQueries,
    identity: IdentityQueries,
) -> ScoresReportDTO:
    snapshots = contents.list_content_snapshots()
    content_ids = [s.content_id for s in snapshots]
    all_evaluations = evaluations.list_for_contents(content_ids)

    by_content: dict[UUID, list[EvaluationDTO]] = {cid: [] for cid in content_ids}
    for evaluation in all_evaluations:
        by_content.setdefault(evaluation.content_id, []).append(evaluation)

    assessor_names = identity.list_assessors(list({e.assessor_id for e in all_evaluations}))

    content_reports = []
    counted_per_assessor: dict[UUID, list[EvaluationDTO]] = {}

    for snapshot in snapshots:
        found = by_content.get(snapshot.content_id, [])
        # Repetitions are corrections: only the latest per assessor counts (ADR-0006).
        counted = aggregation.collapse_latest_per_assessor(found)
        counted_ids = {e.evaluation_id for e in counted}
        for evaluation in counted:
            counted_per_assessor.setdefault(evaluation.assessor_id, []).append(evaluation)

        averages = aggregation.average_by_criterion(found)
        dispersions = aggregation.dispersion_by_criterion(found)

        content_reports.append(
            ContentScoresDTO(
                content_id=snapshot.content_id,
                external_id=snapshot.external_id,
                generating_system=snapshot.generating_system,
                version=snapshot.version,
                average=aggregation.overall_average(found),
                evaluator_count=len(counted),
                criteria=[
                    CriterionSummaryDTO(
                        criterion_id=criterion_id,
                        average=averages[criterion_id],
                        dispersion=dispersions[criterion_id],
                    )
                    for criterion_id in sorted(averages)
                ],
                evaluations=[
                    IndividualEvaluationDTO(
                        evaluation_id=e.evaluation_id,
                        assessor_id=e.assessor_id,
                        assessor_name=_name_of(assessor_names, e.assessor_id),
                        submitted_at=e.submitted_at,
                        # Kept visible, but excluded from every average.
                        superseded=e.evaluation_id not in counted_ids,
                        scores=[
                            ScoreDetailDTO(
                                criterion_id=s.criterion_id, score=s.score, comment=s.comment
                            )
                            for s in e.scores
                        ],
                    )
                    for e in found
                ],
            )
        )

    assessor_reports = [
        AssessorAverageDTO(
            assessor_id=assessor_id,
            display_name=_name_of(assessor_names, assessor_id),
            email=(assessor_names[assessor_id].email if assessor_id in assessor_names else None),
            evaluation_count=len(evaluation_list),
            average=aggregation.overall_average(evaluation_list),
        )
        for assessor_id, evaluation_list in sorted(
            counted_per_assessor.items(), key=lambda item: str(item[0])
        )
    ]

    every_counted = [e for group in counted_per_assessor.values() for e in group]
    return ScoresReportDTO(
        contents=content_reports,
        assessors=assessor_reports,
        global_average=aggregation.overall_average(every_counted),
    )


def _name_of(names: dict, assessor_id: UUID) -> str | None:
    dto = names.get(assessor_id)
    return None if dto is None else (dto.display_name or dto.email)


# --------------------------------------------------------------------------- progress


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
