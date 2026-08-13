"""A study's evaluation runs over HTTP — the console's door onto the batch (ADR-0040).

It lives in the composition root for the same reason `ratification_router.py` does: the act
spans two modules, and wiring two modules' adapters is what a composition root is for. The
routes belong to the study resource all the same; only the file sits outside either module.

The shape is the calibration page's, because the problem is the same one: an evaluation
takes minutes, so a request that waited for it could only ever report at the end. `POST`
starts a run and hands back its id, `GET` reads it while it advances, `POST …/cancel` stops
it. The CLI runs the identical work in the foreground so Ctrl-C reaches it; both doors call
one function.

One thing here is deliberately NOT the run's: **how far a study has got**. Runs are in
memory and die with the process, so the count that matters — how many of the dataset's
courses carry a judgment — is a query over what was persisted. It answers after a restart,
and it answers for a batch someone ran from a terminal, which is exactly what memory cannot
do.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.evaluation_studies.application.report import latest_judgments
from app.modules.evaluation_studies.infrastructure.gateways import (
    EvaluationGateway,
)
from app.modules.evaluation_studies.infrastructure.repository import SqlAlchemyStudyRepository
from app.platform.batch_runs import (
    KEEP_RUNS,
    BatchRefused,
    BatchRun,
    BatchView,
    CourseOutcome,
    batch_runs,
    prepare,
)
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin/studies", tags=["evaluation-studies"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class StartBatchRequest(BaseModel):
    assessor_name: str
    assessor_version: str
    # Courses already evaluated by this assessor under this version are skipped unless this
    # says otherwise — which is what makes re-running the way to resume (ADR-0040 §6).
    re_evaluate: bool = False
    # How many courses at a time. How many REQUESTS may be in flight is the transport's
    # ceiling whatever this says, so raising it cannot burst past `LLM_MAX_CONCURRENCY`.
    concurrency: int | None = None


class BatchRunStartedResponse(BaseModel):
    run_id: UUID


class BatchCourseResponse(BaseModel):
    content_id: UUID
    external_id: str
    # The grouping axis of the fitness (ADR-0039), so the repeats of one commission read
    # together here too.
    brief_id: UUID | None
    status: str
    cause: str | None
    duration_ms: int
    llm_calls: int
    evaluation_id: UUID | None

    @classmethod
    def from_outcome(cls, outcome: CourseOutcome) -> "BatchCourseResponse":
        return cls(
            content_id=outcome.content_id,
            external_id=outcome.external_id,
            brief_id=outcome.brief_id,
            status=outcome.status,
            cause=outcome.cause,
            duration_ms=outcome.duration_ms,
            llm_calls=outcome.llm_calls,
            evaluation_id=outcome.evaluation_id,
        )


class BatchRunResponse(BaseModel):
    run_id: UUID
    study_id: UUID
    instrument_version_id: str
    assessor: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    # Measured on the server, like the dry run's: the page never has to trust two clocks.
    elapsed_ms: int
    total: int
    done: int
    evaluated: int
    failed: int
    skipped: int
    # A RANGE, from the courses this run has already timed, or null until it has timed one.
    # Course durations spread by a factor of two or three, so a single figure would be a
    # promise the work cannot keep (ADR-0040 §9).
    remaining_ms_estimate: list[int] | None
    # The last thing that happened, which is where the criterion in flight shows up. The
    # whole step list is not published: a batch of twenty courses has hundreds, and the
    # per-criterion detail has its own page (`/admin/calibration`).
    current_activity: str | None
    error: str | None
    courses: list[BatchCourseResponse]

    @classmethod
    def from_view(cls, view: BatchView) -> "BatchRunResponse":
        last_step = view.steps[-1] if view.steps else None
        return cls(
            run_id=view.run_id,
            study_id=view.study_id,
            instrument_version_id=view.instrument_version_id,
            assessor=view.package.display_name,
            status=view.status,
            started_at=view.started_at,
            finished_at=view.finished_at,
            elapsed_ms=view.elapsed_ms,
            total=view.total,
            done=view.done,
            evaluated=view.evaluated,
            failed=view.failed,
            skipped=view.skipped,
            remaining_ms_estimate=(
                list(view.remaining_ms_estimate) if view.remaining_ms_estimate is not None else None
            ),
            current_activity=(
                f"{last_step.label}: {last_step.detail}" if last_step is not None else None
            ),
            error=view.error,
            courses=[BatchCourseResponse.from_outcome(o) for o in view.outcomes],
        )


class StudyEvaluationsResponse(BaseModel):
    """What the page opens with: the durable count, and the runs this process remembers."""

    study_id: UUID
    instrument_version_id: str | None
    # Persisted, not remembered: how many of the dataset's courses carry a judgment under
    # the pinned instrument. Survives a restart and counts a batch run from the CLI.
    courses: int
    evaluated: int
    default_concurrency: int
    runs: list[BatchRunResponse]


def _study_or_404(uow: UnitOfWork, study_id: UUID):  # noqa: ANN202 — the domain Study
    study = SqlAlchemyStudyRepository(uow.session).get_by_id(study_id)
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="study not found")
    return study


@router.get("/{study_id}/evaluations", response_model=StudyEvaluationsResponse)
def read_study_evaluations(
    study_id: UUID, admin: AdminAssessor, uow: Uow
) -> StudyEvaluationsResponse:
    """How far this study has been evaluated, and what this process is running for it."""
    study = _study_or_404(uow, study_id)
    evaluated = 0
    if study.instrument_version_id is not None and study.content_ids:
        judgments = EvaluationGateway(uow.session).get_judgments(
            list(study.content_ids), study.instrument_version_id
        )
        # One judgment per content, the current one — the same read the report and the
        # fitness take, so three views of the same study cannot disagree about it.
        evaluated = len(latest_judgments(judgments))
    return StudyEvaluationsResponse(
        study_id=study_id,
        instrument_version_id=study.instrument_version_id,
        courses=len(study.content_ids),
        evaluated=evaluated,
        default_concurrency=get_settings().llm_max_concurrency,
        runs=[BatchRunResponse.from_view(run.view()) for run in batch_runs.for_study(study_id)],
    )


@router.post(
    "/{study_id}/evaluations",
    response_model=BatchRunStartedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_study_evaluation(
    study_id: UUID, request: StartBatchRequest, admin: AdminAssessor, uow: Uow
) -> BatchRunStartedResponse:
    """Start evaluating the whole dataset, and hand back the run's id.

    It spends real LLM calls per course, on the backend's key, which is why it returns
    immediately and is read afterwards. Everything that would fail for every course is
    refused here, before a single call is paid for (ADR-0040 §4).
    """
    _study_or_404(uow, study_id)
    package = AUTOMATED_ASSESSORS.get((request.assessor_name, request.assessor_version))
    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown assessor {request.assessor_name}:{request.assessor_version}",
        )
    workers = request.concurrency or get_settings().llm_max_concurrency

    try:
        run = batch_runs.start(
            prepare(
                study_id=study_id,
                package=package,
                workers=workers,
                re_evaluate=request.re_evaluate,
            )
        )
    except BatchRefused as exc:
        # 409 for the one refusal that is about timing and resolves itself; 422 for the ones
        # that need an act — open the study, pin an instrument, ratify the assessor.
        code = (
            status.HTTP_409_CONFLICT
            if exc.kind == "overlapping_run"
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(
            status_code=code, detail={"kind": exc.kind, "message": str(exc)}
        ) from exc

    return BatchRunStartedResponse(run_id=run.run_id)


def _run_or_404(study_id: UUID, run_id: UUID) -> BatchRun:
    run = batch_runs.get(run_id)
    if run is None or run.study_id != study_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"no evaluation run {run_id} for this study — runs live in memory and only "
                f"the last {KEEP_RUNS} are kept, so a restart or enough newer runs forgets "
                "one. What it evaluated is persisted either way"
            ),
        )
    return run


@router.get("/{study_id}/evaluations/{run_id}", response_model=BatchRunResponse)
def read_study_evaluation_run(
    study_id: UUID, run_id: UUID, admin: AdminAssessor
) -> BatchRunResponse:
    """The run as it stands: every course decided so far, and what is left."""
    return BatchRunResponse.from_view(_run_or_404(study_id, run_id).view())


@router.post(
    "/{study_id}/evaluations/{run_id}/cancel",
    response_model=BatchRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def cancel_study_evaluation_run(
    study_id: UUID, run_id: UUID, admin: AdminAssessor
) -> BatchRunResponse:
    """Stop starting new work. What finished stays; what was in flight persists nothing.

    Accepted rather than done: the workers stop at their next call, so the run is still
    ending when this answers. Cancelling a finished run changes nothing and says so by
    returning it — idempotent, because a second click must not be an error.
    """
    run = _run_or_404(study_id, run_id)
    run.cancel()
    return BatchRunResponse.from_view(run.view())
