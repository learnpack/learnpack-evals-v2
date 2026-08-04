"""Admin read models (08-code.md §7). Reporting is the CQRS query side: no writes, no events."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.evaluand_registry.public import (
    EvaluandRegistryQueries,
    get_evaluand_registry_queries,
)
from app.modules.evaluation.public import EvaluationQueries, get_evaluation_queries
from app.modules.identity.public import IdentityQueries, get_identity_queries
from app.modules.orchestration.public import OrchestrationQueries, get_orchestration_queries
from app.modules.reporting.infrastructure import reports
from app.platform.security import AdminAssessor

router = APIRouter(prefix="/admin", tags=["reporting"])

Contents = Annotated[EvaluandRegistryQueries, Depends(get_evaluand_registry_queries)]
Evaluations = Annotated[EvaluationQueries, Depends(get_evaluation_queries)]
Identity = Annotated[IdentityQueries, Depends(get_identity_queries)]
Orchestration = Annotated[OrchestrationQueries, Depends(get_orchestration_queries)]


class DispersionResponse(BaseModel):
    """Inter-rater spread. Null with a single rater — nothing to agree on (ADR-0006)."""

    stdev: float | None
    mean_pairwise_abs_diff: float | None
    exact_agreement_pct: float | None
    rater_count: int


class ScoreDetailResponse(BaseModel):
    criterion_id: str
    score: int
    comment: str | None


class IndividualEvaluationResponse(BaseModel):
    evaluation_id: UUID
    assessor_id: UUID
    assessor_name: str | None
    submitted_at: datetime | None
    superseded: bool
    scores: list[ScoreDetailResponse]


class CriterionSummaryResponse(BaseModel):
    criterion_id: str
    average: float
    dispersion: DispersionResponse


class ContentScoresResponse(BaseModel):
    content_id: UUID
    external_id: str
    package_format: str
    version: str
    average: float | None
    evaluator_count: int
    criteria: list[CriterionSummaryResponse]
    evaluations: list[IndividualEvaluationResponse]


class AssessorAverageResponse(BaseModel):
    assessor_id: UUID
    display_name: str | None
    email: str | None
    evaluation_count: int
    average: float | None


class ScoresReportResponse(BaseModel):
    contents: list[ContentScoresResponse]
    assessors: list[AssessorAverageResponse]
    global_average: float | None


class AssignmentCountsResponse(BaseModel):
    assigned: int
    opened: int
    submitted: int
    cancelled: int
    pending: int


class AssessorProgressResponse(BaseModel):
    assessor_id: UUID
    display_name: str | None
    counts: AssignmentCountsResponse


class ContentProgressRowResponse(BaseModel):
    content_id: UUID
    external_id: str
    counts: AssignmentCountsResponse


class ProgressReportResponse(BaseModel):
    by_assessor: list[AssessorProgressResponse]
    by_content: list[ContentProgressRowResponse]


def _counts(counts) -> AssignmentCountsResponse:  # noqa: ANN001 — internal DTO
    return AssignmentCountsResponse(
        assigned=counts.assigned,
        opened=counts.opened,
        submitted=counts.submitted,
        cancelled=counts.cancelled,
        pending=counts.pending,
    )


@router.get("/reports/scores", response_model=ScoresReportResponse)
def scores_report(
    admin: AdminAssessor,
    contents: Contents,
    evaluations: Evaluations,
    identity: Identity,
) -> ScoresReportResponse:
    """Scores per course (individual and averaged), per evaluator, global, and inter-rater."""
    report = reports.build_scores_report(contents, evaluations, identity)
    return ScoresReportResponse(
        contents=[
            ContentScoresResponse(
                content_id=c.content_id,
                external_id=c.external_id,
                package_format=c.package_format,
                version=c.version,
                average=c.average,
                evaluator_count=c.evaluator_count,
                criteria=[
                    CriterionSummaryResponse(
                        criterion_id=criterion.criterion_id,
                        average=criterion.average,
                        dispersion=DispersionResponse(
                            stdev=criterion.dispersion.stdev,
                            mean_pairwise_abs_diff=criterion.dispersion.mean_pairwise_abs_diff,
                            exact_agreement_pct=criterion.dispersion.exact_agreement_pct,
                            rater_count=criterion.dispersion.rater_count,
                        ),
                    )
                    for criterion in c.criteria
                ],
                evaluations=[
                    IndividualEvaluationResponse(
                        evaluation_id=e.evaluation_id,
                        assessor_id=e.assessor_id,
                        assessor_name=e.assessor_name,
                        submitted_at=e.submitted_at,
                        superseded=e.superseded,
                        scores=[
                            ScoreDetailResponse(
                                criterion_id=s.criterion_id, score=s.score, comment=s.comment
                            )
                            for s in e.scores
                        ],
                    )
                    for e in c.evaluations
                ],
            )
            for c in report.contents
        ],
        assessors=[
            AssessorAverageResponse(
                assessor_id=a.assessor_id,
                display_name=a.display_name,
                email=a.email,
                evaluation_count=a.evaluation_count,
                average=a.average,
            )
            for a in report.assessors
        ],
        global_average=report.global_average,
    )


@router.get("/progress", response_model=ProgressReportResponse)
def progress_report(
    admin: AdminAssessor,
    orchestration: Orchestration,
    contents: Contents,
    identity: Identity,
) -> ProgressReportResponse:
    """Who evaluated what / what is pending, per evaluator and per course."""
    report = reports.build_progress_report(orchestration, contents, identity)
    return ProgressReportResponse(
        by_assessor=[
            AssessorProgressResponse(
                assessor_id=a.assessor_id,
                display_name=a.display_name,
                counts=_counts(a.counts),
            )
            for a in report.by_assessor
        ],
        by_content=[
            ContentProgressRowResponse(
                content_id=c.content_id, external_id=c.external_id, counts=_counts(c.counts)
            )
            for c in report.by_content
        ],
    )
