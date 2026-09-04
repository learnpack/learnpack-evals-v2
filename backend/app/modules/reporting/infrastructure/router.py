"""Admin read models (08-code.md §7). Reporting is the CQRS query side: no writes, no events."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.evaluand_registry.public import (
    EvaluandRegistryQueries,
    get_evaluand_registry_queries,
)
from app.modules.evaluation.public import EvaluationQueries, get_evaluation_queries
from app.modules.evaluation_design.public import (
    InstrumentQueries,
    RubricQueries,
    get_instrument_queries,
    get_rubric_queries,
)
from app.modules.identity.public import IdentityQueries, get_identity_queries
from app.modules.orchestration.public import OrchestrationQueries, get_orchestration_queries
from app.modules.reporting.infrastructure import campaign_report, claim_validity, reports
from app.platform.security import AdminAssessor

router = APIRouter(prefix="/admin", tags=["reporting"])

Contents = Annotated[EvaluandRegistryQueries, Depends(get_evaluand_registry_queries)]
Evaluations = Annotated[EvaluationQueries, Depends(get_evaluation_queries)]
Identity = Annotated[IdentityQueries, Depends(get_identity_queries)]
Orchestration = Annotated[OrchestrationQueries, Depends(get_orchestration_queries)]
Rubrics = Annotated[RubricQueries, Depends(get_rubric_queries)]
Instruments = Annotated[InstrumentQueries, Depends(get_instrument_queries)]


class ScoreDetailResponse(BaseModel):
    quality_id: str
    # Null is an abstention — see `ScoreDetailDTO`.
    score: int | None
    comment: str | None
    derived: bool = False


class IndividualEvaluationResponse(BaseModel):
    evaluation_id: UUID
    assessor_id: UUID
    assessor_name: str | None
    submitted_at: datetime | None
    superseded: bool
    scores: list[ScoreDetailResponse]


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


# ------------------------------------------------------ the campaign report (ADR-0060)


class ItemAgreementResponse(BaseModel):
    """Null everywhere below one pair — see `ItemAgreement`."""

    pair_count: int
    content_count: int
    mean_abs_diff: float | None
    exact_pct: float | None
    within_one_pct: float | None


class ItemSummaryResponse(BaseModel):
    # Keyed by point of the scale, every point present including the ones nobody chose.
    distribution: dict[int, int]
    average: float | None
    scored_count: int
    # Asked and answered "I could not judge this" (ADR-0052 §4).
    abstentions: int
    # Not asked at all: the course declares nothing the item is about (ADR-0053). A different
    # fact from an abstention, and the reason the two travel in separate fields.
    withheld_contents: int
    answered_contents: int
    agreement: ItemAgreementResponse


class ItemReportResponse(BaseModel):
    quality_id: str
    order: int
    dimension: str
    prompt: str
    required_data: list[str]
    summary: ItemSummaryResponse


class ContentDisagreementResponse(BaseModel):
    mean_abs_diff: float | None
    max_abs_diff: int | None
    contested_items: int


class CampaignContentResponse(BaseModel):
    content_id: UUID
    external_id: str
    title: str | None
    submitted_count: int
    required: int
    completed: bool
    disagreement: ContentDisagreementResponse
    evaluations: list[IndividualEvaluationResponse]


class CampaignInstrumentResponse(BaseModel):
    instrument_version_id: str
    name: str
    version: str
    response_format: str
    scale_min: int
    scale_max: int


class CampaignQuorumResponse(BaseModel):
    contents_in_scope: int
    contents_complete: int
    coverage: float
    required_per_content: int
    evaluations_counted: int
    evaluations_expected: int
    superseded_count: int
    assessor_count: int


class CampaignReportResponse(BaseModel):
    """One campaign's result, read at the grain of the item (ADR-0060).

    Composed on read, never frozen: a campaign's record is the golden reference its own policy
    establishes, so there is no signed document here and `status` is what tells a reader
    whether they are looking at a finished round.
    """

    campaign_id: UUID
    name: str
    description: str | None
    status: str
    dataset_version_id: UUID | None
    instrument: CampaignInstrumentResponse
    quorum: CampaignQuorumResponse
    items: list[ItemReportResponse]
    contents: list[CampaignContentResponse]


@router.get("/campaigns/{campaign_id}/report", response_model=CampaignReportResponse)
def campaign_report_endpoint(
    campaign_id: UUID,
    admin: AdminAssessor,
    orchestration: Orchestration,
    evaluations: Evaluations,
    contents: Contents,
    identity: Identity,
    rubrics: Rubrics,
) -> CampaignReportResponse:
    """What this campaign found: per item across the scope, then per course."""
    try:
        report = campaign_report.build_campaign_report(
            campaign_id, orchestration, evaluations, contents, identity, rubrics
        )
    except campaign_report.InstrumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"the pinned reference instrument '{exc}' is not in the store",
        ) from exc
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")

    return CampaignReportResponse(
        campaign_id=report.campaign_id,
        name=report.name,
        description=report.description,
        status=report.status,
        dataset_version_id=report.dataset_version_id,
        instrument=CampaignInstrumentResponse(
            instrument_version_id=report.instrument.instrument_version_id,
            name=report.instrument.name,
            version=report.instrument.version,
            response_format=report.instrument.response_format,
            scale_min=report.instrument.scale_min,
            scale_max=report.instrument.scale_max,
        ),
        quorum=CampaignQuorumResponse(
            contents_in_scope=report.quorum.contents_in_scope,
            contents_complete=report.quorum.contents_complete,
            coverage=report.quorum.coverage,
            required_per_content=report.quorum.required_per_content,
            evaluations_counted=report.quorum.evaluations_counted,
            evaluations_expected=report.quorum.evaluations_expected,
            superseded_count=report.quorum.superseded_count,
            assessor_count=report.quorum.assessor_count,
        ),
        items=[
            ItemReportResponse(
                quality_id=item.quality_id,
                order=item.order,
                dimension=item.dimension,
                prompt=item.prompt,
                required_data=item.required_data,
                summary=ItemSummaryResponse(
                    distribution=item.summary.distribution,
                    average=item.summary.average,
                    scored_count=item.summary.scored_count,
                    abstentions=item.summary.abstentions,
                    withheld_contents=item.summary.withheld_contents,
                    answered_contents=item.summary.answered_contents,
                    agreement=ItemAgreementResponse(
                        pair_count=item.summary.agreement.pair_count,
                        content_count=item.summary.agreement.content_count,
                        mean_abs_diff=item.summary.agreement.mean_abs_diff,
                        exact_pct=item.summary.agreement.exact_pct,
                        within_one_pct=item.summary.agreement.within_one_pct,
                    ),
                ),
            )
            for item in report.items
        ],
        contents=[
            CampaignContentResponse(
                content_id=content.content_id,
                external_id=content.external_id,
                title=content.title,
                submitted_count=content.submitted_count,
                required=content.required,
                completed=content.completed,
                disagreement=ContentDisagreementResponse(
                    mean_abs_diff=content.disagreement.mean_abs_diff,
                    max_abs_diff=content.disagreement.max_abs_diff,
                    contested_items=content.disagreement.contested_items,
                ),
                evaluations=[
                    IndividualEvaluationResponse(
                        evaluation_id=e.evaluation_id,
                        assessor_id=e.assessor_id,
                        assessor_name=e.assessor_name,
                        submitted_at=e.submitted_at,
                        superseded=e.superseded,
                        scores=[
                            ScoreDetailResponse(
                                quality_id=s.quality_id,
                                score=s.score,
                                comment=s.comment,
                                derived=s.derived,
                            )
                            for s in e.scores
                        ],
                    )
                    for e in content.evaluations
                ],
            )
            for content in report.contents
        ],
    )


# --------------------------------------------------------------------------- claim validity


class RatioResponse(BaseModel):
    """A proportion with its denominator: `9 of 11` and `82 %` are not the same assertion."""

    hit: int
    of: int


class HumanAnswerResponse(BaseModel):
    """One expert's number on this item, and what they wrote beside it."""

    assessor_id: UUID
    assessor_name: str | None
    score: int
    comment: str | None


class CitedFindingResponse(BaseModel):
    """What the assessor raised, in its own words. Null quote only on an absence-derived fail."""

    criterion_id: str
    failure_mode: str
    quote: str | None
    locator: dict[str, Any] | None


class DiscordantCourseResponse(BaseModel):
    """A course where the two sides contradicted each other — both readings, neither corrected."""

    content_id: UUID
    external_id: str
    title: str | None
    cell: str
    human_mean: float
    # Null when only one expert answered: one opinion is not a disagreement.
    experts_agree: bool | None
    answers: list[HumanAnswerResponse]
    evidence_basis: dict[str, int]
    # Empty whenever the assessor said `supported` — it raised nothing, and that is the finding.
    findings: list[CitedFindingResponse]


class ClaimValidityResponse(BaseModel):
    claim_id: str
    statement: str
    quality_id: str
    dimension: str | None
    sample: int
    sensitivity: RatioResponse
    specificity: RatioResponse
    # Null, never 0, wherever the table cannot support the number (ADR-0063 §3).
    kappa: float | None
    youden_j: float | None
    judge_agreement: float | None
    human_agreement: float | None
    grey: int
    unanswered: int
    insufficient: int
    status: str
    reason: str | None
    discordant: list[DiscordantCourseResponse]


class ClaimValidityReportResponse(BaseModel):
    campaign_id: UUID
    campaign_name: str
    assessor_id: UUID
    assessor_name: str | None
    instrument_version_id: str
    instrument_name: str
    courses_in_campaign: int
    courses_judged: int
    claims: list[ClaimValidityResponse]


@router.get("/validity", response_model=ClaimValidityReportResponse)
def claim_validity_endpoint(
    campaign: UUID,
    assessor: UUID,
    instrument: str,
    admin: AdminAssessor,
    orchestration: Orchestration,
    evaluations: Evaluations,
    contents: Contents,
    rubrics: Rubrics,
    instruments: Instruments,
    identity: Identity,
) -> ClaimValidityReportResponse:
    """How much each claim of this assessor follows the panel of that campaign (ADR-0063).

    The three coordinates are query parameters and all three are required here. What ADR-0063
    §7 makes optional is the *campaign a reader chooses*, and a reader that chose none has no
    verdict to ask for — which is why the option lives on the screen and not in this signature.

    Not a sub-resource of the campaign: what is being qualified is the pair
    `(assessor version, claim)`, and the campaign is what it was measured against.
    """
    try:
        report = claim_validity.build_claim_validity(
            campaign,
            assessor,
            instrument,
            orchestration,
            evaluations,
            contents,
            rubrics,
            instruments,
            identity,
        )
    except campaign_report.InstrumentUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"the campaign's pinned reference instrument '{exc}' is not in the store",
        ) from exc
    except claim_validity.InstrumentNotPublished as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"instrument '{exc}' not found"
        ) from exc
    except claim_validity.AssessorUnknown as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"assessor '{exc}' not found"
        ) from exc
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")

    return ClaimValidityReportResponse(
        campaign_id=report.campaign_id,
        campaign_name=report.campaign_name,
        assessor_id=report.assessor_id,
        assessor_name=report.assessor_name,
        instrument_version_id=report.instrument_version_id,
        instrument_name=report.instrument_name,
        courses_in_campaign=report.courses_in_campaign,
        courses_judged=report.courses_judged,
        claims=[
            ClaimValidityResponse(
                claim_id=c.claim_id,
                statement=c.statement,
                quality_id=c.quality_id,
                dimension=c.dimension,
                sample=c.sample,
                sensitivity=RatioResponse(hit=c.sensitivity.hit, of=c.sensitivity.of),
                specificity=RatioResponse(hit=c.specificity.hit, of=c.specificity.of),
                kappa=c.kappa,
                youden_j=c.youden_j,
                judge_agreement=c.judge_agreement,
                human_agreement=c.human_agreement,
                grey=c.grey,
                unanswered=c.unanswered,
                insufficient=c.insufficient,
                status=c.status,
                reason=c.reason,
                discordant=[
                    DiscordantCourseResponse(
                        content_id=d.content_id,
                        external_id=d.external_id,
                        title=d.title,
                        cell=d.cell,
                        human_mean=d.human_mean,
                        experts_agree=d.experts_agree,
                        answers=[
                            HumanAnswerResponse(
                                assessor_id=a.assessor_id,
                                assessor_name=a.assessor_name,
                                score=a.score,
                                comment=a.comment,
                            )
                            for a in d.answers
                        ],
                        evidence_basis=d.evidence_basis,
                        findings=[
                            CitedFindingResponse(
                                criterion_id=f.criterion_id,
                                failure_mode=f.failure_mode,
                                quote=f.quote,
                                locator=f.locator,
                            )
                            for f in d.findings
                        ],
                    )
                    for d in c.discordant
                ],
            )
            for c in report.claims
        ],
    )
