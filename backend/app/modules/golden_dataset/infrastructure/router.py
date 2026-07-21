"""Admin read endpoint for the golden reference (`getGoldenReference`, 07-define.md)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.golden_dataset.domain.golden_dataset import is_usable
from app.modules.golden_dataset.public import (
    GoldenDatasetQueries,
    get_golden_dataset_queries,
)
from app.modules.orchestration.public import OrchestrationQueries, get_orchestration_queries
from app.platform.security import AdminAssessor

router = APIRouter(prefix="/admin/campaigns", tags=["golden-dataset"])

Golden = Annotated[GoldenDatasetQueries, Depends(get_golden_dataset_queries)]
Orchestration = Annotated[OrchestrationQueries, Depends(get_orchestration_queries)]


class GoldenStatusResponse(BaseModel):
    campaign_id: UUID
    rubric_version_id: str
    coverage: float
    threshold: float
    usable: bool
    established_at: str | None = None


@router.get("/{campaign_id}/golden", response_model=GoldenStatusResponse)
def golden_status(
    campaign_id: UUID, admin: AdminAssessor, golden: Golden, orchestration: Orchestration
) -> GoldenStatusResponse:
    progress = orchestration.get_campaign_progress(campaign_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")

    reference = golden.get_golden_reference(campaign_id, progress.rubric_version_id)
    return GoldenStatusResponse(
        campaign_id=campaign_id,
        rubric_version_id=progress.rubric_version_id,
        coverage=progress.coverage,
        threshold=progress.golden_coverage_threshold,
        # Live coverage, so the answer is right even before the policy has run.
        usable=is_usable(progress.coverage, progress.golden_coverage_threshold),
        established_at=(
            reference.established_at.isoformat() if reference and reference.established_at else None
        ),
    )
