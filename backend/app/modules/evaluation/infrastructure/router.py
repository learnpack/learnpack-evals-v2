"""HTTP adapter for `SubmitEvaluation` (08-code.md §7).

The endpoint takes an `assignmentId`, but an `Evaluation` is campaign-agnostic (ADR-0005).
It therefore resolves the assignment through Orchestration's **public query surface**
(a read-only sync query, allowed by 05-connect.md rule 2) and never issues a cross-module
command: the assignment becomes `submitted` because the completion policy hears
`EvaluationSubmitted`.

Note what is *not* imported here: no repository or adapter of another module — only their
`public.py` (ARCHITECTURE.md §3).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.evaluation.application.submit_evaluation import (
    ScoreInput,
    SubmitEvaluation,
    SubmitEvaluationCommand,
)
from app.modules.evaluation.domain.evaluation import InvalidEvaluation
from app.modules.evaluation.infrastructure.repository import SqlAlchemyEvaluationRepository
from app.modules.evaluation_design.public import RubricQueries, get_rubric_queries
from app.modules.orchestration.public import OrchestrationQueries, get_orchestration_queries
from app.platform.security import CurrentAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/evaluations", tags=["evaluation"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]
Orchestration = Annotated[OrchestrationQueries, Depends(get_orchestration_queries)]
Rubrics = Annotated[RubricQueries, Depends(get_rubric_queries)]


class ScoreRequest(BaseModel):
    criterion_id: str
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class SubmitEvaluationRequest(BaseModel):
    assignment_id: UUID
    scores: list[ScoreRequest]


class EvaluationResponse(BaseModel):
    evaluation_id: UUID
    assessor_id: UUID
    content_id: UUID
    instrument_version_id: str
    scores: list[ScoreRequest]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=EvaluationResponse)
def submit_evaluation(
    request: SubmitEvaluationRequest,
    assessor: CurrentAssessor,
    uow: Uow,
    orchestration: Orchestration,
    rubrics: Rubrics,
) -> EvaluationResponse:
    assignment = orchestration.get_assignment(request.assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assignment not found")
    if assignment.assessor_id != assessor.assessor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your assignment")
    if assignment.is_cancelled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="assignment was cancelled")
    # One submission per assignment — human anti-duplication lives here, not in a uniqueness
    # constraint on Evaluation (ADR-0005).
    #
    # NOTE: two concurrent submissions could both pass this check. With a handful of SMEs
    # that is theoretical, and benign: the quorum counts assignments submitted, so an extra
    # evaluation cannot inflate it.
    if assignment.is_submitted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="this assignment has already been submitted",
        )

    rubric = rubrics.get_rubric(assignment.instrument_version_id)
    if rubric is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rubric not found")

    use_case = SubmitEvaluation(
        evaluations=SqlAlchemyEvaluationRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        evaluation = use_case(
            SubmitEvaluationCommand(
                assessor_id=assessor.assessor_id,
                content_id=assignment.content_id,
                instrument_version_id=assignment.instrument_version_id,
                scores=[
                    ScoreInput(criterion_id=s.criterion_id, score=s.score, comment=s.comment)
                    for s in request.scores
                ],
                rubric_criterion_ids=rubric.criterion_ids,
            )
        )
    except InvalidEvaluation as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return EvaluationResponse(
        evaluation_id=evaluation.id,
        assessor_id=evaluation.assessor_id,
        content_id=evaluation.content_id,
        instrument_version_id=evaluation.instrument_version_id,
        scores=[
            ScoreRequest(criterion_id=s.criterion_id, score=s.score, comment=s.comment)
            for s in evaluation.result.scores
        ],
    )
