"""HTTP adapters for Orchestration: admin campaign/assignment management + the evaluator's
to-do list (08-code.md §7).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.evaluand_registry.public import (
    EvaluandRegistryQueries,
    get_evaluand_registry_queries,
)
from app.modules.evaluation_design.public import RubricQueries, get_rubric_queries
from app.modules.orchestration.application import queries
from app.modules.orchestration.application.commands import (
    AssignContent,
    AssignContentCommand,
    AssignmentNotFound,
    CampaignNotFound,
    CancelAssignment,
    CloseCampaign,
    ContentNotInCampaign,
    DuplicateAssignment,
    InvalidCampaign,
    OpenAssignment,
    OpenCampaign,
    OpenCampaignCommand,
)
from app.modules.orchestration.domain.assignment import InvalidAssignmentTransition
from app.modules.orchestration.infrastructure.repository import (
    SqlAlchemyAssignmentRepository,
    SqlAlchemyCampaignRepository,
)
from app.platform.security import AdminAssessor, CurrentAssessor
from app.platform.uow import UnitOfWork, get_uow

Uow = Annotated[UnitOfWork, Depends(get_uow)]
# Other modules are reached only through their public query surface (ARCHITECTURE.md §3).
Contents = Annotated[EvaluandRegistryQueries, Depends(get_evaluand_registry_queries)]
Rubrics = Annotated[RubricQueries, Depends(get_rubric_queries)]

admin_router = APIRouter(prefix="/admin", tags=["orchestration-admin"])
evaluator_router = APIRouter(tags=["orchestration"])


# --------------------------------------------------------------------------- schemas


class OpenCampaignRequest(BaseModel):
    rubric_version_id: str = Field(examples=["learnpack-pedagogical-v1"])
    required_evaluations_per_content: int = Field(ge=1, examples=[2])
    content_ids: list[UUID]
    metadata_view: list[str] = Field(default_factory=list)
    golden_coverage_threshold: float = 1.0


class AssignContentRequest(BaseModel):
    content_id: UUID
    assessor_id: UUID


class CampaignResponse(BaseModel):
    campaign_id: UUID
    rubric_version_id: str
    required_evaluations_per_content: int
    content_ids: list[UUID]
    metadata_view: list[str]
    status: str


class AssignmentResponse(BaseModel):
    assignment_id: UUID
    campaign_id: UUID
    content_id: UUID
    assessor_id: UUID
    status: str
    rubric_version_id: str


class ContentProgressResponse(BaseModel):
    content_id: UUID
    submitted_count: int
    required: int
    completed: bool


class CampaignProgressResponse(BaseModel):
    campaign_id: UUID
    rubric_version_id: str
    status: str
    required_evaluations_per_content: int
    coverage: float
    contents: list[ContentProgressResponse]


class MetadataEntryResponse(BaseModel):
    key: str
    value: object
    value_type: str


class CriterionResponse(BaseModel):
    criterion_id: str
    order: int
    dimension: str
    prompt: str
    guidance: str
    anchor_low: str
    anchor_high: str


class AssignmentDetailResponse(BaseModel):
    """Everything the 3-step evaluator flow needs (08-code.md §7)."""

    assignment_id: UUID
    status: str
    content_id: UUID
    consumable_url: str
    metadata: list[MetadataEntryResponse]
    rubric_version_id: str
    scale_min: int
    scale_max: int
    criteria: list[CriterionResponse]


# --------------------------------------------------------------------------- helpers


def _campaign_response(campaign) -> CampaignResponse:  # noqa: ANN001 — domain aggregate
    return CampaignResponse(
        campaign_id=campaign.id,
        rubric_version_id=campaign.rubric_version_id,
        required_evaluations_per_content=campaign.required_evaluations_per_content,
        content_ids=campaign.content_ids,
        metadata_view=campaign.metadata_view,
        status=str(campaign.status),
    )


def _assignment_response(assignment, rubric_version_id: str) -> AssignmentResponse:  # noqa: ANN001
    return AssignmentResponse(
        assignment_id=assignment.id,
        campaign_id=assignment.campaign_id,
        content_id=assignment.content_id,
        assessor_id=assignment.assessor_id,
        status=str(assignment.status),
        rubric_version_id=rubric_version_id,
    )


# --------------------------------------------------------------------------- admin


@admin_router.get("/campaigns", response_model=list[CampaignResponse])
def list_campaigns(admin: AdminAssessor, uow: Uow) -> list[CampaignResponse]:
    """Every campaign, newest-created last — the admin console's campaign list."""
    campaigns = SqlAlchemyCampaignRepository(uow.session).list_all()
    return [_campaign_response(c) for c in campaigns]


@admin_router.post(
    "/campaigns", status_code=status.HTTP_201_CREATED, response_model=CampaignResponse
)
def open_campaign(
    request: OpenCampaignRequest, admin: AdminAssessor, uow: Uow, rubrics: Rubrics
) -> CampaignResponse:
    rubric = rubrics.get_rubric(request.rubric_version_id)
    if rubric is None or not rubric.is_published:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="rubric version must exist and be published",
        )

    use_case = OpenCampaign(
        campaigns=SqlAlchemyCampaignRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        campaign = use_case(
            OpenCampaignCommand(
                rubric_version_id=request.rubric_version_id,
                required_evaluations_per_content=request.required_evaluations_per_content,
                content_ids=request.content_ids,
                metadata_view=request.metadata_view,
                golden_coverage_threshold=request.golden_coverage_threshold,
            )
        )
    except InvalidCampaign as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _campaign_response(campaign)


@admin_router.post(
    "/campaigns/{campaign_id}/assignments",
    status_code=status.HTTP_201_CREATED,
    response_model=AssignmentResponse,
)
def assign_content(
    campaign_id: UUID, request: AssignContentRequest, admin: AdminAssessor, uow: Uow
) -> AssignmentResponse:
    campaigns = SqlAlchemyCampaignRepository(uow.session)
    use_case = AssignContent(
        campaigns=campaigns,
        assignments=SqlAlchemyAssignmentRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        assignment = use_case(
            AssignContentCommand(
                campaign_id=campaign_id,
                content_id=request.content_id,
                assessor_id=request.assessor_id,
            )
        )
    except CampaignNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc
    except DuplicateAssignment as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ContentNotInCampaign, InvalidCampaign) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    campaign = campaigns.get(campaign_id)
    return _assignment_response(assignment, campaign.rubric_version_id)


@admin_router.post("/assignments/{assignment_id}/cancel", response_model=AssignmentResponse)
def cancel_assignment(assignment_id: UUID, admin: AdminAssessor, uow: Uow) -> AssignmentResponse:
    campaigns = SqlAlchemyCampaignRepository(uow.session)
    use_case = CancelAssignment(
        assignments=SqlAlchemyAssignmentRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        assignment = use_case(assignment_id)
    except AssignmentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="assignment not found"
        ) from exc
    except InvalidAssignmentTransition as exc:
        # A submitted assignment cannot be cancelled (ADR-0002).
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    campaign = campaigns.get(assignment.campaign_id)
    return _assignment_response(assignment, campaign.rubric_version_id)


@admin_router.post("/campaigns/{campaign_id}/close", response_model=CampaignResponse)
def close_campaign(campaign_id: UUID, admin: AdminAssessor, uow: Uow) -> CampaignResponse:
    use_case = CloseCampaign(
        campaigns=SqlAlchemyCampaignRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        campaign = use_case(campaign_id)
    except CampaignNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found"
        ) from exc
    except InvalidCampaign as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _campaign_response(campaign)


@admin_router.get("/campaigns/{campaign_id}/assignments", response_model=list[AssignmentResponse])
def list_campaign_assignments(
    campaign_id: UUID, admin: AdminAssessor, uow: Uow
) -> list[AssignmentResponse]:
    """Every assignment in a campaign — the roster the admin cancels/reassigns from."""
    campaigns = SqlAlchemyCampaignRepository(uow.session)
    campaign = campaigns.get(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    assignments = SqlAlchemyAssignmentRepository(uow.session).list_for_campaign(campaign_id)
    return [_assignment_response(a, campaign.rubric_version_id) for a in assignments]


@admin_router.get("/campaigns/{campaign_id}/progress", response_model=CampaignProgressResponse)
def campaign_progress(
    campaign_id: UUID, admin: AdminAssessor, uow: Uow
) -> CampaignProgressResponse:
    progress = queries.get_campaign_progress(
        SqlAlchemyAssignmentRepository(uow.session),
        SqlAlchemyCampaignRepository(uow.session),
        campaign_id,
    )
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    return CampaignProgressResponse(
        campaign_id=progress.campaign_id,
        rubric_version_id=progress.rubric_version_id,
        status=progress.status,
        required_evaluations_per_content=progress.required_evaluations_per_content,
        coverage=progress.coverage,
        contents=[
            ContentProgressResponse(
                content_id=c.content_id,
                submitted_count=c.submitted_count,
                required=c.required,
                completed=c.completed,
            )
            for c in progress.contents
        ],
    )


# --------------------------------------------------------------------------- evaluator


@evaluator_router.get("/me/assignments", response_model=list[AssignmentResponse])
def my_assignments(assessor: CurrentAssessor, uow: Uow) -> list[AssignmentResponse]:
    pending = queries.get_pending_assignments(
        SqlAlchemyAssignmentRepository(uow.session),
        SqlAlchemyCampaignRepository(uow.session),
        assessor.assessor_id,
    )
    return [
        AssignmentResponse(
            assignment_id=a.assignment_id,
            campaign_id=a.campaign_id,
            content_id=a.content_id,
            assessor_id=a.assessor_id,
            status=a.status,
            rubric_version_id=a.rubric_version_id,
        )
        for a in pending
    ]


@evaluator_router.get("/assignments/{assignment_id}", response_model=AssignmentDetailResponse)
def assignment_detail(
    assignment_id: UUID,
    assessor: CurrentAssessor,
    uow: Uow,
    contents: Contents,
    rubrics: Rubrics,
) -> AssignmentDetailResponse:
    """Composes three modules through their public query surfaces — no cross-module JOINs."""
    assignment = queries.get_assignment(
        SqlAlchemyAssignmentRepository(uow.session),
        SqlAlchemyCampaignRepository(uow.session),
        assignment_id,
    )
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignment not found")
    if assignment.assessor_id != assessor.assessor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your assignment")

    snapshot = contents.get_content_snapshot(assignment.content_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
    # Which keys the evaluator sees is the campaign's call (ADR-0001).
    snapshot = snapshot.filtered(assignment.metadata_view or None)

    rubric = rubrics.get_rubric(assignment.rubric_version_id)
    if rubric is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rubric not found")

    return AssignmentDetailResponse(
        assignment_id=assignment.assignment_id,
        status=assignment.status,
        content_id=snapshot.content_id,
        consumable_url=snapshot.consumable_url,
        metadata=[
            MetadataEntryResponse(key=e.key, value=e.value, value_type=e.value_type)
            for e in snapshot.metadata
        ],
        rubric_version_id=rubric.rubric_version_id,
        scale_min=rubric.scale_min,
        scale_max=rubric.scale_max,
        criteria=[
            CriterionResponse(
                criterion_id=c.criterion_id,
                order=c.order,
                dimension=c.dimension,
                prompt=c.prompt,
                guidance=c.guidance,
                anchor_low=c.anchor_low,
                anchor_high=c.anchor_high,
            )
            for c in rubric.criteria
        ],
    )


@evaluator_router.post("/assignments/{assignment_id}/open", response_model=AssignmentResponse)
def open_assignment(assignment_id: UUID, assessor: CurrentAssessor, uow: Uow) -> AssignmentResponse:
    assignments = SqlAlchemyAssignmentRepository(uow.session)
    existing = assignments.get(assignment_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignment not found")
    if existing.assessor_id != assessor.assessor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your assignment")

    use_case = OpenAssignment(assignments=assignments, publisher=uow.events, uow=uow)
    try:
        assignment = use_case(assignment_id)
    except InvalidAssignmentTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    campaign = SqlAlchemyCampaignRepository(uow.session).get(assignment.campaign_id)
    return _assignment_response(assignment, campaign.rubric_version_id)
