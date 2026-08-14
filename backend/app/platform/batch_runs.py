"""Evaluating a whole study: many courses, one bounded, cancellable, watchable run.

A generation of the optimization experiment is a study's worth of courses, and each course
is ~16 LLM calls today and ~40 once the criteria that read every lesson exist. Run one at a
time that is hours; run them without a ceiling and the account's rate limit decides how it
goes. So this is a **run**, in the shape `preview_runs.py` already established: started and
not awaited, reporting while it works, remembered in memory. The differences are the ones
that matter for real work — it persists, it uses several workers, and it can be stopped.

**Batch is a loop over the existing use case** (ADR-0027 §3, one level up): each course is a
plain `EvaluateContent`, with its own session and its own transaction. Nothing here knows
how a criterion is judged.

It lives in the composition root because it names two modules' adapters — the study on one
side, the evaluation on the other — which only the composition root may do
(ARCHITECTURE.md §3, `tests/test_architecture.py`). It is also what keeps the rule that
studies never command Evaluation: the study is read here, not asked to do anything.

Three things bound the cost, and each answers a different way of losing money:

- **How many calls are in flight** is not decided here at all. The workers only decide how
  many courses are open at once; the ceiling on requests lives in the transport
  (`LLM_MAX_CONCURRENCY`), which is the only place that sees every call however many levels
  of fan-out sit above it. When criteria that fan out over lessons arrive, they will nest
  inside this loop and the ceiling will still hold, unchanged.
- **What is already done is not redone.** By default a course this assessor already
  evaluated under this instrument version is skipped, so a batch that died halfway is
  resumed by running it again.
- **What is going to fail for everyone fails once.** A configuration failure and a coverage
  bug are the same for every course, so the first one ends the batch; a run of transport
  failures means the endpoint is gone, so three in a row end it too; and a failure nobody
  named — a database missing a column, say — ends it as well, because an unrecognised cause
  is the one you cannot assume is this course's alone. Everything else is one course's
  problem and the batch keeps going (ADR-0037 decides what happens *inside* an evaluation;
  this decides what happens between them). However a batch ends, the course that ended it is
  named in the summary: `failed` and `cancelled` are different endings and a reader must be
  able to tell "I stopped it" from "it stopped itself".

Cancelling means **stop starting**: courses that finished stay finished, the ones in flight
stop at their next call, and nothing needs undoing — an evaluation that does not reach its
end persists nothing.
"""

import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from app.modules.evaluation.application.evaluate_content import (
    AssessorNotRatified,
    EvaluateContent,
    EvaluateContentCommand,
    InstrumentNotEvaluable,
    ProfileNotAvailable,
)
from app.modules.evaluation.domain.model import InvalidAutomatedEvaluation
from app.modules.evaluation.infrastructure.assessors import AssessorPackage
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.modules.evaluation.infrastructure.gateways import DesignInstrumentGateway, ProfilingGateway
from app.modules.evaluation.infrastructure.preview_runs import RunStep, with_progress
from app.modules.evaluation.infrastructure.repository import (
    SqlAlchemyAutomatedEvaluationRepository,
    SqlAlchemyRatificationRepository,
)
from app.modules.evaluation_studies.application.dtos import ContentInfo
from app.modules.evaluation_studies.infrastructure.gateways import (
    RegistryGateway as StudiesRegistryGateway,
)
from app.modules.evaluation_studies.infrastructure.repository import SqlAlchemyStudyRepository
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform import cancellation, observability
from app.platform.cancellation import CancellationToken, Cancelled, cancel_scope
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork

logger = logging.getLogger(__name__)

RunStatus = Literal["running", "done", "cancelled", "failed", "refused"]
CourseStatus = Literal["evaluated", "skipped", "failed", "cancelled"]

# Consecutive courses that may die of transport before the batch concludes the endpoint is
# gone. Three because two can be coincidence on a flaky network and the fourth would be
# money spent on a diagnosis already made. The transport has already spent its own retry
# budget on each of them (`llm.MAX_TRANSPORT_ATTEMPTS`), so this is failure after failure,
# not impatience.
TRANSPORT_FAILURE_STREAK = 3

# Failure kinds that are a property of the wiring, identical for every course: the first one
# ends the batch instead of proving itself nineteen more times.
FATAL_FAILURE_KINDS = frozenset({"configuration"})

# How many runs the process remembers. Fewer than the dry runs keep: a batch is a deliberate
# act nobody fires twenty times in a session, and what outlives the process is what it wrote.
KEEP_RUNS = 10


class BatchRefused(Exception):
    """The batch cannot start, and no course would have succeeded. Named, never generic."""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class CourseOutcome:
    """What became of one course. `cause` is filled exactly when something went wrong."""

    content_id: UUID
    external_id: str
    brief_id: UUID | None
    status: CourseStatus
    cause: str | None = None
    duration_ms: int = 0
    llm_calls: int = 0
    evaluation_id: UUID | None = None


@dataclass(frozen=True)
class BatchView:
    """A consistent read of a run while the workers keep working on the original."""

    run_id: UUID
    study_id: UUID
    package: AssessorPackage
    instrument_version_id: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    elapsed_ms: int
    total: int
    done: int
    evaluated: int
    failed: int
    skipped: int
    outcomes: Sequence[CourseOutcome]
    steps: Sequence[RunStep]
    error: str | None
    remaining_ms_estimate: tuple[int, int] | None

    @property
    def pending(self) -> int:
        return max(0, self.total - self.done)


class BatchRun:
    """One study's evaluation in flight, or the memory of one that ended."""

    def __init__(
        self,
        *,
        run_id: UUID,
        study_id: UUID,
        instrument_version_id: str,
        assessor_id: UUID,
        package: AssessorPackage,
        courses: Sequence[ContentInfo],
        already_evaluated: Sequence[UUID],
        workers: int,
    ) -> None:
        self.run_id = run_id
        self.study_id = study_id
        self.instrument_version_id = instrument_version_id
        self.assessor_id = assessor_id
        self.package = package
        self.courses = list(courses)
        self.workers = workers
        self.token = CancellationToken()
        # An extra listener for the LLM attempts, when the caller wants them printed or
        # written to a trace. The run always counts its own; this is who else hears them.
        self.sink: observability.Sink | None = None
        self.started_at = datetime.now(UTC)
        self.status: RunStatus = "running"
        self.finished_at: datetime | None = None
        self.error: str | None = None
        done_before = set(already_evaluated)
        self._outcomes: list[CourseOutcome] = [
            CourseOutcome(
                content_id=content.content_id,
                external_id=content.external_id,
                brief_id=content.brief_id,
                status="skipped",
                cause="already evaluated by this assessor under this instrument version",
            )
            for content in courses
            if content.content_id in done_before
        ]
        self.pending = [c for c in courses if c.content_id not in done_before]
        self._steps: list[RunStep] = []
        self._durations: list[int] = []
        self._transport_streak = 0
        self._failure: str | None = None
        self._started = time.monotonic()
        self._ended: float | None = None
        self._lock = threading.Lock()

    # --- what the workers report into -----------------------------------------------------

    def _elapsed_ms(self) -> int:
        end = self._ended if self._ended is not None else time.monotonic()
        return int((end - self._started) * 1000)

    def record_step(self, step: RunStep) -> None:
        with self._lock:
            self._steps.append(
                RunStep(
                    kind=step.kind,
                    label=step.label,
                    detail=step.detail,
                    ok=step.ok,
                    duration_ms=step.duration_ms,
                    at_ms=self._elapsed_ms(),
                )
            )

    def record_course(self, outcome: CourseOutcome) -> None:
        with self._lock:
            self._outcomes.append(outcome)
            if outcome.status == "evaluated":
                self._durations.append(outcome.duration_ms)
                # A course that got through is the endpoint answering: whatever run of
                # transport failures preceded it was weather, not an outage.
                self._transport_streak = 0
        self.record_step(
            RunStep(
                kind="criterion",
                label=outcome.external_id,
                detail=outcome.status
                if outcome.cause is None
                else f"{outcome.status}: {outcome.cause}",
                ok=outcome.status in {"evaluated", "skipped"},
                duration_ms=outcome.duration_ms,
            )
        )

    def note_failure_kind(self, kind: str) -> bool:
        """Record a course's failure kind; answer whether the batch should stop.

        The streak counts CONSECUTIVE transport deaths — any course that completes clears it
        (`record_course`), so only a sustained outage ends the run.
        """
        with self._lock:
            if kind in FATAL_FAILURE_KINDS:
                return True
            if kind == "transport":
                self._transport_streak += 1
                return self._transport_streak >= TRANSPORT_FAILURE_STREAK
            self._transport_streak = 0
            return False

    def cancel(self) -> None:
        """Someone asked it to stop. The only ending a person causes."""
        self.token.cancel()

    def fail(self, cause: str) -> None:
        """A failure ended it — the run stops starting, and says a failure is why.

        Distinct from `cancel` on purpose: both stop the same way, and a reader needs to
        tell "I stopped it" from "it stopped itself", because only one of the two is a
        reason to go looking for a cause.
        """
        with self._lock:
            if self._failure is None:
                self._failure = cause
        self.token.cancel()

    def finish(self, error: str | None = None) -> None:
        with self._lock:
            self._ended = time.monotonic()
            self.finished_at = datetime.now(UTC)
            self.error = self._failure or error
            if self._failure is not None:
                self.status = "failed"
            elif self.token.is_cancelled:
                self.status = "cancelled"
            elif error is not None:
                self.status = "refused"
            else:
                self.status = "done"

    # --- what a reader sees ---------------------------------------------------------------

    def _estimate(self, pending: int) -> tuple[int, int] | None:
        """A range, from what THIS run has measured, or nothing until it has measured.

        A range and not a number because course durations here spread by a factor of two or
        three — a draft's size and how many judgements need a third sample both move it —
        and a single figure would be a promise the work cannot keep.
        """
        if not self._durations or pending == 0:
            return None
        ordered = sorted(self._durations)
        typical = ordered[len(ordered) // 2]
        slowest = ordered[-1]
        lanes = max(1, min(self.workers, pending))
        rounds = -(-pending // lanes)  # ceiling division: how many waves are left
        return (typical * rounds, slowest * rounds)

    def view(self) -> BatchView:
        with self._lock:
            outcomes = tuple(self._outcomes)
            evaluated = sum(1 for o in outcomes if o.status == "evaluated")
            failed = sum(1 for o in outcomes if o.status == "failed")
            skipped = sum(1 for o in outcomes if o.status == "skipped")
            total = len(self.courses)
            done = len(outcomes)
            return BatchView(
                run_id=self.run_id,
                study_id=self.study_id,
                package=self.package,
                instrument_version_id=self.instrument_version_id,
                status=self.status,
                started_at=self.started_at,
                finished_at=self.finished_at,
                elapsed_ms=self._elapsed_ms(),
                total=total,
                done=done,
                evaluated=evaluated,
                failed=failed,
                skipped=skipped,
                outcomes=outcomes,
                steps=tuple(self._steps),
                error=self.error,
                remaining_ms_estimate=self._estimate(total - done),
            )


# --- starting one ---------------------------------------------------------------------------


def prepare(
    *,
    study_id: UUID,
    package: AssessorPackage,
    workers: int,
    re_evaluate: bool = False,
) -> BatchRun:
    """Everything that can be refused, refused before a single call is paid for.

    Each check below fails identically for every course in the dataset, which is what makes
    it belong here rather than in the loop: discovering it on course nineteen would cost
    eighteen courses' worth of money to learn what course one already knew.
    """
    with SessionLocal() as session:
        study = SqlAlchemyStudyRepository(session).get_by_id(study_id)
        if study is None:
            raise BatchRefused(f"study {study_id} is not declared", kind="study_not_found")
        if study.status != "open":
            raise BatchRefused(
                f"study {study_id} is {study.status}: a batch evaluates an OPEN study, whose "
                "dataset is fixed (open-study first, or publish-study if it is finished)",
                kind="study_not_open",
            )
        instrument_version_id = study.instrument_version_id
        if instrument_version_id is None:
            raise BatchRefused(
                f"study {study_id} has no instrument pinned — pin-study first",
                kind="instrument_not_pinned",
            )
        if not study.content_ids:
            raise BatchRefused(
                f"study {study_id} has an empty dataset — compose-dataset first",
                kind="dataset_empty",
            )

        assessor = SqlAlchemyAssessorRepository(session).get_automated(
            package.name, package.version
        )
        if assessor is None:
            raise BatchRefused(
                f"{package.display_name} is not registered — run ratify-assessor first",
                kind="assessor_not_registered",
            )
        if not SqlAlchemyRatificationRepository(session).is_ratified(
            assessor.id, instrument_version_id
        ):
            raise BatchRefused(
                f"{package.display_name} has not ratified {instrument_version_id} (ADR-0019) — "
                "run ratify-assessor first; without it no judgment may persist",
                kind="assessor_not_ratified",
            )

        registry = StudiesRegistryGateway(session)
        courses = sorted(
            registry.get_contents_by_ids(list(study.content_ids)),
            key=lambda c: c.external_id,
        )
        already: list[UUID] = []
        if not re_evaluate:
            evaluations = SqlAlchemyAutomatedEvaluationRepository(session)
            already = [
                content.content_id
                for content in courses
                if evaluations.next_attempt(assessor.id, content.content_id, instrument_version_id)
                > 1
            ]

    return BatchRun(
        run_id=uuid4(),
        study_id=study_id,
        instrument_version_id=instrument_version_id,
        assessor_id=assessor.id,
        package=package,
        courses=courses,
        already_evaluated=already,
        workers=workers,
    )


def execute(run: BatchRun) -> None:
    """Run every pending course, at most `run.workers` at a time. Never raises.

    Blocking on purpose: whoever wants it asynchronous starts a thread around this call. The
    CLI wants it in the foreground so Ctrl-C reaches it; the console starts it through
    `batch_runs.start` and reads the run by its id. One function, two doors.
    """
    try:
        with ThreadPoolExecutor(max_workers=max(1, run.workers)) as pool:
            for _ in pool.map(lambda course: _evaluate_one(run, course), run.pending):
                pass
    except Exception as exc:  # noqa: BLE001 — a run has nowhere to raise
        logger.exception("batch run %s failed unexpectedly", run.run_id)
        run.finish(error=f"{type(exc).__name__}: {exc}")
        return
    run.finish()


class BatchRunRegistry:
    """The batches this process is running, or has just run. In memory, like the dry runs.

    What is durable about a batch is what it wrote — the evaluations — so a run object is
    only the live view of one, and forgetting it on restart costs nothing that a query
    cannot answer (ADR-0040 §9).

    It carries one rule of its own: **a batch may not overlap a running one.** Judgments are
    append-only and every reader takes the most recent per content, so two batches over one
    course decide by arrival order — the only genuinely confusing outcome available here, and
    the cheapest one to refuse. Batches over disjoint studies still run together; how many
    requests that puts in flight is the transport's ceiling, not this registry's business.
    """

    def __init__(self, keep: int = KEEP_RUNS) -> None:
        self._runs: OrderedDict[UUID, BatchRun] = OrderedDict()
        self._keep = keep
        self._lock = threading.Lock()

    def start(self, run: BatchRun) -> BatchRun:
        with self._lock:
            self._refuse_overlap(run)
            self._runs[run.run_id] = run
            while len(self._runs) > self._keep:
                self._forget_oldest_finished()
        # Daemon: an evaluation must never hold the API process open on shutdown.
        threading.Thread(
            target=execute, args=(run,), name=f"batch-{run.run_id}", daemon=True
        ).start()
        return run

    def _refuse_overlap(self, run: BatchRun) -> None:
        wanted = {course.content_id for course in run.pending}
        for other in self._runs.values():
            if other.status != "running":
                continue
            if wanted & {course.content_id for course in other.pending}:
                raise BatchRefused(
                    f"batch {other.run_id} is already evaluating courses this one would "
                    "evaluate: two runs over one course decide by arrival order, since every "
                    "reader takes the most recent judgment. Wait for it, or cancel it",
                    kind="overlapping_run",
                )

    def _forget_oldest_finished(self) -> None:
        """Drop the oldest run that has ENDED. A running one is never forgotten — its thread
        is still reporting into it, and it is the one someone is watching."""
        ended = next(
            (run_id for run_id, run in self._runs.items() if run.status != "running"), None
        )
        if ended is not None:
            del self._runs[ended]
            return
        self._runs.popitem(last=False)  # every kept run is running: the oldest goes anyway

    def get(self, run_id: UUID) -> BatchRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def for_study(self, study_id: UUID) -> list[BatchRun]:
        """Newest first — what a page shows under "this study's runs"."""
        with self._lock:
            return [run for run in reversed(self._runs.values()) if run.study_id == study_id]


# One registry per process, like the dry runs' and the event dispatcher's. The API reads it;
# the CLI runs its batch in the foreground and never touches it.
batch_runs = BatchRunRegistry()


def _evaluate_one(run: BatchRun, course: ContentInfo) -> None:
    """One course, in its own thread: its own scopes, its own session, its own transaction."""
    if run.token.is_cancelled:
        run.record_course(_cancelled(course))
        return

    calls: list[observability.LlmCall] = []
    started = time.monotonic()
    # Installed HERE and not by the starter: a worker thread begins with an empty context,
    # so this is what makes the token, the trace and the memoization this course's own.
    scope = run.package.cache_scope() if run.package.cache_scope else nullcontext()
    sink = observability.fan_out(calls.append, run.sink) if run.sink else calls.append
    try:
        with cancel_scope(run.token), scope, observability.collecting(sink):
            cancellation.check()
            evaluation_id = _run_use_case(run, course)
    except Cancelled:
        run.record_course(_cancelled(course))
        return
    except ProfileNotAvailable as exc:
        # This course's own problem: the others may well be profiled.
        run.record_course(_failed(course, str(exc), started, calls))
        return
    except (InstrumentNotEvaluable, AssessorNotRatified) as exc:
        # Checked before the batch started, so reaching here means the wiring changed under
        # it — true for every remaining course, and not worth proving nineteen more times.
        run.record_course(_failed(course, str(exc), started, calls))
        run.fail(f"{course.external_id}: {exc}")
        return
    except AssessorExecutionError as exc:
        # Past the evaluation's own failure budget (ADR-0037 §3): nothing persisted for this
        # course. Whether the batch continues depends on whether the cause is this course's.
        run.record_course(_failed(course, f"{exc} [{exc.kind}]", started, calls))
        if run.note_failure_kind(exc.kind):
            run.fail(f"{course.external_id}: {exc} [{exc.kind}]")
        return
    except InvalidAutomatedEvaluation as exc:
        # A registration bug: this assessor's coverage does not match this instrument, which
        # is true for every course in the dataset. Never softened, never repeated.
        run.record_course(_failed(course, str(exc), started, calls))
        run.fail(f"{course.external_id}: {exc}")
        return
    except Exception as exc:  # noqa: BLE001 — a worker thread has nowhere to raise
        # Not a failure this loop knows how to place. It ends the batch, because a cause
        # nobody named is the one you cannot assume belongs to this course — a database
        # missing a column is every course's — and it says WHICH course met it, which an
        # exception escaping to the runner would not.
        logger.exception(
            "course %s failed unexpectedly in batch %s", course.external_id, run.run_id
        )
        run.record_course(_failed(course, f"{type(exc).__name__}: {exc}", started, calls))
        run.fail(f"{course.external_id}: {type(exc).__name__}: {exc}")
        return

    run.record_course(
        CourseOutcome(
            content_id=course.content_id,
            external_id=course.external_id,
            brief_id=course.brief_id,
            status="evaluated",
            duration_ms=int((time.monotonic() - started) * 1000),
            llm_calls=len(calls),
            evaluation_id=evaluation_id,
        )
    )


def _run_use_case(run: BatchRun, course: ContentInfo) -> UUID:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = EvaluateContent(
            evaluations=SqlAlchemyAutomatedEvaluationRepository(session),
            instruments=DesignInstrumentGateway(session),
            profiles=ProfilingGateway(session),
            ratifications=SqlAlchemyRatificationRepository(session),
            coverage=run.package.coverage,
            executors=with_progress(
                run.package.executors,
                lambda step: run.record_step(
                    RunStep(
                        kind=step.kind,
                        label=f"{course.external_id} · {step.label}",
                        detail=step.detail,
                        ok=step.ok,
                        duration_ms=step.duration_ms,
                    )
                ),
            ),
            publisher=uow.events,
            uow=uow,
        )
        evaluation = use_case(
            EvaluateContentCommand(
                content_id=course.content_id,
                instrument_version_id=run.instrument_version_id,
                assessor_id=run.assessor_id,
            )
        )
        return evaluation.id


def _cancelled(course: ContentInfo) -> CourseOutcome:
    return CourseOutcome(
        content_id=course.content_id,
        external_id=course.external_id,
        brief_id=course.brief_id,
        status="cancelled",
        cause="the run was cancelled before this course was evaluated",
    )


def _failed(
    course: ContentInfo, cause: str, started: float, calls: Sequence[observability.LlmCall]
) -> CourseOutcome:
    return CourseOutcome(
        content_id=course.content_id,
        external_id=course.external_id,
        brief_id=course.brief_id,
        status="failed",
        cause=cause,
        duration_ms=int((time.monotonic() - started) * 1000),
        llm_calls=len(calls),
    )
