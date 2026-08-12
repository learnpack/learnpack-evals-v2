"""HTTP adapter for `SubmitEvaluation` (08-code.md §7).

The endpoint takes an `assignmentId`, but an `Evaluation` is campaign-agnostic (ADR-0005).
It therefore resolves the assignment through Orchestration's **public query surface**
(a read-only sync query, allowed by 05-connect.md rule 2) and never issues a cross-module
command: the assignment becomes `submitted` because the completion policy hears
`EvaluationSubmitted`.

Note what is *not* imported here: no repository or adapter of another module — only their
`public.py` (ARCHITECTURE.md §3).

`admin_router` is the automated path's admin surface: the assessor-package registry and
the dry-run (`PreviewEvaluation`) exposed for the calibration page. The dry-run is pure
computation — it persists nothing, so exposing it is not a command reaching a page; the
deliberate acts (profile, accept, ratify, evaluate for real) stay in the CLI.

The dry-run is started, not awaited: with LLM-carried criteria it takes minutes, and a
request that long can only report at the end. `POST …/preview` returns a run id, and the
run is read while it advances (`preview_runs`). Only the assessor is validated up front —
everything else a run can hit becomes the run's own error, so the page reads every ending
from one place.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.evaluation.application.preview_evaluation import (
    Preview,
    PreviewEvaluationCommand,
)
from app.modules.evaluation.application.submit_evaluation import (
    ScoreInput,
    SubmitEvaluation,
    SubmitEvaluationCommand,
)
from app.modules.evaluation.domain.evaluation import InvalidEvaluation
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS, AssessorPackage
from app.modules.evaluation.infrastructure.preview_runs import KEEP_RUNS, RunView, preview_runs
from app.modules.evaluation.infrastructure.repository import SqlAlchemyEvaluationRepository
from app.modules.evaluation_design.public import RubricQueries, get_rubric_queries
from app.modules.orchestration.public import OrchestrationQueries, get_orchestration_queries
from app.platform.security import AdminAssessor, CurrentAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/evaluations", tags=["evaluation"])
admin_router = APIRouter(prefix="/admin", tags=["automated-evaluation"])

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


# --------------------------------------------------- the automated path's admin surface


class AssessorPackageResponse(BaseModel):
    """One registry entry — identity and coverage, never the executors (callables)."""

    name: str
    version: str
    display_name: str
    instrument_id: str
    executes: list[str]
    abstains: dict[str, str]
    # Whether the package carries LLM tasks: the page warns about cost and the backend's
    # LLM_API_KEY. Environment concern only — the identity is in the code (ADR-0034).
    uses_llm: bool

    @classmethod
    def from_package(cls, package: AssessorPackage) -> "AssessorPackageResponse":
        return cls(
            name=package.name,
            version=package.version,
            display_name=package.display_name,
            instrument_id=package.instrument_id,
            executes=sorted(package.coverage.executes),
            abstains=dict(sorted(package.coverage.abstains.items())),
            uses_llm="llm" in package.source_config,
        )


class PreviewEvaluationRequest(BaseModel):
    content_id: UUID
    instrument_version_id: str
    assessor_name: str
    assessor_version: str


class PreviewOutcomeResponse(BaseModel):
    criterion_id: str
    outcome: str
    derived: bool
    quote: str | None
    locator: dict[str, Any] | None
    failure_mode: str | None


class PreviewClaimResponse(BaseModel):
    claim_id: str
    status: str
    # Keys stay camelCase inside on purpose: this dict is the domain's own vocabulary
    # (`pass`, `noEvidence`, …), the same one persisted judgments carry.
    evidence_basis: dict[str, int]


class PreviewFindingResponse(BaseModel):
    claim_id: str
    criterion_id: str
    failure_mode: str
    quote: str | None
    locator: dict[str, Any] | None


class PreviewMetricResponse(BaseModel):
    metric_id: str
    value: Any


class PreviewAssessorResponse(BaseModel):
    name: str
    version: str
    display_name: str


class PreviewEvaluationResponse(BaseModel):
    instrument_version_id: str
    # The page badges a draft run as calibration; the dry-run accepts drafts by design.
    instrument_status: str
    assessor: PreviewAssessorResponse
    outcomes: list[PreviewOutcomeResponse]
    claims: list[PreviewClaimResponse]
    findings: list[PreviewFindingResponse]
    coverage: dict[str, Any]
    metrics: list[PreviewMetricResponse]
    # The contract states what the page claims: a dry-run never persists anything.
    persisted: Literal[False] = False

    @classmethod
    def from_preview(
        cls, preview: Preview, package: AssessorPackage
    ) -> "PreviewEvaluationResponse":
        return cls(
            instrument_version_id=preview.instrument.instrument_version_id,
            instrument_status=preview.instrument.status,
            assessor=PreviewAssessorResponse(
                name=package.name, version=package.version, display_name=package.display_name
            ),
            outcomes=[
                PreviewOutcomeResponse(
                    criterion_id=o.criterion_id,
                    outcome=o.outcome,
                    derived=o.derived,
                    quote=o.quote,
                    locator=dict(o.locator) if o.locator is not None else None,
                    failure_mode=o.failure_mode,
                )
                for o in preview.outcomes
            ],
            claims=[
                PreviewClaimResponse(
                    claim_id=c.claim_id, status=c.status, evidence_basis=dict(c.evidence_basis)
                )
                for c in preview.judgment.claims
            ],
            findings=[
                PreviewFindingResponse(
                    claim_id=f.claim_id,
                    criterion_id=f.criterion_id,
                    failure_mode=f.failure_mode,
                    quote=f.quote,
                    locator=dict(f.locator) if f.locator is not None else None,
                )
                for f in preview.judgment.findings
            ],
            coverage=dict(preview.judgment.coverage),
            metrics=[
                PreviewMetricResponse(metric_id=m.metric_id, value=m.value) for m in preview.metrics
            ],
        )


@admin_router.get("/assessor-packages", response_model=list[AssessorPackageResponse])
def list_assessor_packages(admin: AdminAssessor) -> list[AssessorPackageResponse]:
    """The in-code registry, as data: what can judge, over which lineage, at what cost."""
    return [
        AssessorPackageResponse.from_package(package)
        for _, package in sorted(AUTOMATED_ASSESSORS.items())
    ]


class PreviewRunStepResponse(BaseModel):
    """One thing the run did, in the order it did it."""

    kind: str
    label: str
    detail: str
    ok: bool
    duration_ms: int
    at_ms: int


class PreviewRunErrorResponse(BaseModel):
    # Named, not merely described: the page turns each kind into the remedy that fixes it.
    kind: str
    message: str


class PreviewRunStartedResponse(BaseModel):
    run_id: UUID


class PreviewRunResponse(BaseModel):
    run_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    # Measured on the server: the page never has to trust two clocks agreeing.
    elapsed_ms: int
    steps: list[PreviewRunStepResponse]
    result: PreviewEvaluationResponse | None
    error: PreviewRunErrorResponse | None

    @classmethod
    def from_view(cls, view: RunView) -> "PreviewRunResponse":
        return cls(
            run_id=view.run_id,
            status=view.status,
            started_at=view.started_at,
            finished_at=view.finished_at,
            elapsed_ms=view.elapsed_ms,
            steps=[
                PreviewRunStepResponse(
                    kind=step.kind,
                    label=step.label,
                    detail=step.detail,
                    ok=step.ok,
                    duration_ms=step.duration_ms,
                    at_ms=step.at_ms,
                )
                for step in view.steps
            ],
            result=(
                PreviewEvaluationResponse.from_preview(view.preview, view.package)
                if view.preview is not None
                else None
            ),
            error=(
                PreviewRunErrorResponse(kind=view.error.kind, message=view.error.message)
                if view.error is not None
                else None
            ),
        )


class LlmCallResponse(BaseModel):
    """One attempt, whole: what was asked, what came back, what it cost."""

    task_id: str | None
    attempt: int
    model_requested: str
    model_answered: str | None
    provider: str | None
    # Temperature, output budget, response format, whatever the assessor pinned: the half
    # of "what was asked" that is not the conversation, and decides the answer just as much.
    sampling: dict[str, Any]
    messages: list[dict[str, str]]
    response_text: str | None
    finish_reason: str | None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    error: str | None


class PreviewRunTraceResponse(BaseModel):
    run_id: UUID
    status: str
    # Where the same records were written, when the machine asked for a trace file. Runs
    # are forgotten on restart; the file is not.
    trace_path: str | None
    calls: list[LlmCallResponse]


@admin_router.post(
    "/evaluations/preview",
    response_model=PreviewRunStartedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_preview_evaluation(
    request: PreviewEvaluationRequest, admin: AdminAssessor
) -> PreviewRunStartedResponse:
    """Start the dry-run and hand back its id — the calibration page's engine.

    Same use case as the CLI's `evaluate --dry-run`: accepts drafts, needs no
    ratification, persists nothing. An LLM-carrying package spends real calls and takes
    minutes, which is why this returns immediately and the run is read afterwards.

    Only the assessor is validated here, because it is a lookup in the in-code registry.
    A missing profile or an unknown instrument version is discovered by the run itself
    and becomes its error, so every way a run can end is read from one place."""
    package = AUTOMATED_ASSESSORS.get((request.assessor_name, request.assessor_version))
    if package is None:
        known = ", ".join(f"{n}:{v}" for n, v in sorted(AUTOMATED_ASSESSORS))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"unknown assessor {request.assessor_name}:{request.assessor_version} "
                f"(registry has: {known})"
            ),
        )
    run = preview_runs.start(
        package,
        PreviewEvaluationCommand(
            content_id=request.content_id,
            instrument_version_id=request.instrument_version_id,
        ),
    )
    return PreviewRunStartedResponse(run_id=run.run_id)


def _run_or_404(run_id: UUID) -> RunView:
    view = preview_runs.get(run_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"no dry run {run_id} — runs live in memory and only the last "
                f"{KEEP_RUNS} are kept, so a restart or enough newer runs forgets one"
            ),
        )
    return view


@admin_router.get("/evaluations/preview/{run_id}", response_model=PreviewRunResponse)
def read_preview_run(run_id: UUID, admin: AdminAssessor) -> PreviewRunResponse:
    """The run as it stands: its steps so far, and its result or its error once it ends."""
    return PreviewRunResponse.from_view(_run_or_404(run_id))


@admin_router.get("/evaluations/preview/{run_id}/trace", response_model=PreviewRunTraceResponse)
def read_preview_run_trace(run_id: UUID, admin: AdminAssessor) -> PreviewRunTraceResponse:
    """Every LLM attempt of the run, whole — the prompts as sent and the raw answers.

    Untruncated on purpose: an abridged prompt cannot be compared against the one that
    produced a different answer, which is the only reason to read this at all."""
    view = _run_or_404(run_id)
    return PreviewRunTraceResponse(
        run_id=view.run_id,
        status=view.status,
        trace_path=str(view.trace_path) if view.trace_path is not None else None,
        calls=[LlmCallResponse(**call.as_record()) for call in view.calls],
    )
