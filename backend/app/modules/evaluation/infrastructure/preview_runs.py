"""The dry-run as a job: it reports while it works instead of after it finishes.

A dry-run with LLM-carried criteria takes minutes. As one blocking request it could only
ever say two things, both at the end — here is everything, or it failed — and the failure
arrived as a toast the browser may not have been showing. So the HTTP call now starts a
run and returns its id; the page reads the run while it advances.

What a run reports is one stream seen live: every criterion the derivation executes and
every LLM attempt the transport makes (`app.platform.observability`). The same records
are kept whole as the run's trace, which is the only way to read the prompt a task sent
and the raw text it got back.

**Nothing is persisted.** The registry is in memory and bounded, exactly so the dry-run's
contract survives being asynchronous: no evaluation row, no event, no judgment — and no
run table either. A restarted process forgets its runs; that is the correct trade for a
calibration tool, and a trace file is what outlives the process.

The task memoization is cleared at the start of every run. It is keyed by profile and
lives as long as the process, so without this a second run over the same profile would
report the first run's `llm_*` spend as if it had paid it, and would show an empty trace.
Runs are assumed not to overlap in the calibration loop; two concurrent ones over the
same profile would re-ask rather than reuse, which costs calls but decides nothing
differently.
"""

import dataclasses
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from app.modules.evaluation.application.evaluate_content import (
    InstrumentNotEvaluable,
    ProfileNotAvailable,
)
from app.modules.evaluation.application.preview_evaluation import (
    Preview,
    PreviewEvaluation,
    PreviewEvaluationCommand,
)
from app.modules.evaluation.domain.derivation import Executor
from app.modules.evaluation.domain.model import CriterionSpec, ExecutorResult, ProfileData
from app.modules.evaluation.infrastructure.assessors import AssessorPackage
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.modules.evaluation.infrastructure.gateways import DesignInstrumentGateway, ProfilingGateway
from app.platform import observability
from app.platform.db import SessionLocal

logger = logging.getLogger(__name__)

RunStatus = Literal["running", "done", "failed"]

# Why a run ended without a verdict. The page turns each into the remedy that fixes it,
# which is the whole reason the cause is named rather than merely described.
ErrorKind = Literal["profile_missing", "instrument_missing", "assessor_failed", "unexpected"]

# Enough to compare a handful of calibration attempts, few enough that whole prompts and
# raw answers in memory stay a rounding error. The oldest run is dropped, not the newest:
# what you are looking at is what you just ran.
KEEP_RUNS = 20


@dataclass(frozen=True)
class RunStep:
    """One thing that happened, in the order it happened."""

    kind: Literal["criterion", "llm_call"]
    label: str
    detail: str
    ok: bool
    duration_ms: int
    # Milliseconds from the start of the run to the moment this was recorded. Stamped by
    # the run: a reporter knows how long it took, not when the run began.
    at_ms: int = 0


@dataclass(frozen=True)
class RunError:
    kind: ErrorKind
    message: str


@dataclass(frozen=True)
class RunView:
    """A consistent read of a run: the worker keeps working on the original."""

    run_id: UUID
    package: AssessorPackage
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    elapsed_ms: int
    steps: Sequence[RunStep]
    calls: Sequence[observability.LlmCall]
    preview: Preview | None
    error: RunError | None
    trace_path: Path | None


class PreviewRun:
    """One dry-run in flight, or the memory of one that finished."""

    def __init__(
        self, run_id: UUID, package: AssessorPackage, command: PreviewEvaluationCommand
    ) -> None:
        self.run_id = run_id
        self.package = package
        self.command = command
        self.started_at = datetime.now(UTC)
        self.status: RunStatus = "running"
        self.finished_at: datetime | None = None
        self.preview: Preview | None = None
        self.error: RunError | None = None
        # Where this run's attempts are also written, when the machine asked for a trace
        # file. In-memory runs are few and die with the process; the file is what lets
        # yesterday's calibration attempt be compared against today's.
        self.trace_path: Path | None = observability.trace_path(str(run_id))
        self._steps: list[RunStep] = []
        self._calls: list[observability.LlmCall] = []
        self._started = time.monotonic()
        self._ended: float | None = None
        self._lock = threading.Lock()

    def _elapsed_ms(self) -> int:
        """Measured server-side, so the page never has to trust two clocks agreeing."""
        end = self._ended if self._ended is not None else time.monotonic()
        return int((end - self._started) * 1000)

    def record_step(self, step: RunStep) -> None:
        with self._lock:
            self._steps.append(dataclasses.replace(step, at_ms=self._elapsed_ms()))

    def record_call(self, call: observability.LlmCall) -> None:
        """The sink handed to the transport: one record per attempt, kept whole."""
        with self._lock:
            self._calls.append(call)
        self.record_step(
            RunStep(
                kind="llm_call",
                label=call.task_id or "llm call",
                detail=_call_detail(call),
                ok=call.ok,
                duration_ms=call.latency_ms,
            )
        )

    def finish(self, *, preview: Preview | None = None, error: RunError | None = None) -> None:
        with self._lock:
            self.preview = preview
            self.error = error
            self.status = "done" if error is None else "failed"
            self._ended = time.monotonic()
            self.finished_at = datetime.now(UTC)

    def view(self) -> RunView:
        with self._lock:
            return RunView(
                run_id=self.run_id,
                package=self.package,
                status=self.status,
                started_at=self.started_at,
                finished_at=self.finished_at,
                elapsed_ms=self._elapsed_ms(),
                steps=tuple(self._steps),
                calls=tuple(self._calls),
                preview=self.preview,
                error=self.error,
                trace_path=self.trace_path,
            )


def _call_detail(call: observability.LlmCall) -> str:
    if call.error:
        return f"attempt {call.attempt} · {call.error}"
    detail = f"attempt {call.attempt} · {call.tokens_in}→{call.tokens_out} tokens"
    if call.finish_reason and call.finish_reason != "stop":
        # Loud on purpose: `length` means the answer was cut off, and it reaches the
        # caller as "the answer is not valid JSON", which names the symptom, not the cause.
        detail = f"{detail} · finish_reason={call.finish_reason}"
    return detail


def with_progress(
    executors: Mapping[str, Executor], report: Callable[[RunStep], None]
) -> dict[str, Executor]:
    """The same executors, each announcing its verdict as it lands.

    Wrapping happens HERE, at the composition root, and not one layer deeper: the
    derivation stays pure (executors in, outcomes out) and no assessor package learns
    that anyone is watching.
    """

    def wrapped(criterion_id: str, executor: Executor) -> Executor:
        def traced(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
            started = time.monotonic()
            try:
                result = executor(spec, profile)
            except Exception as exc:
                report(
                    RunStep(
                        kind="criterion",
                        label=criterion_id,
                        detail=f"{type(exc).__name__}: {exc}",
                        ok=False,
                        duration_ms=int((time.monotonic() - started) * 1000),
                    )
                )
                raise
            report(
                RunStep(
                    kind="criterion",
                    label=criterion_id,
                    detail="pass" if result.passed else "fail",
                    ok=True,  # a `fail` is a verdict, not a malfunction
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            )
            return result

        return traced

    return {criterion_id: wrapped(criterion_id, fn) for criterion_id, fn in executors.items()}


class PreviewRunRegistry:
    """The last few dry-runs, in memory, each on its own thread."""

    def __init__(self, keep: int = KEEP_RUNS) -> None:
        self._runs: OrderedDict[UUID, PreviewRun] = OrderedDict()
        self._keep = keep
        self._lock = threading.Lock()

    def start(self, package: AssessorPackage, command: PreviewEvaluationCommand) -> PreviewRun:
        run = PreviewRun(run_id=uuid4(), package=package, command=command)
        with self._lock:
            self._runs[run.run_id] = run
            while len(self._runs) > self._keep:
                self._runs.popitem(last=False)
        # Daemon: a calibration run must never hold the API process open on shutdown.
        threading.Thread(
            target=execute, args=(run,), name=f"preview-{run.run_id}", daemon=True
        ).start()
        return run

    def get(self, run_id: UUID) -> RunView | None:
        with self._lock:
            run = self._runs.get(run_id)
        return run.view() if run is not None else None


def execute(run: PreviewRun) -> None:
    """The worker: its own session, its own sink, and every ending accounted for.

    Its own session because the request's dies with the response. Every ending because a
    thread has nowhere to raise: an unhandled exception here would leave the page polling
    a run that never finishes.
    """
    sink: observability.Sink = run.record_call
    if run.trace_path is not None:
        sink = observability.fan_out(sink, observability.jsonl_sink(run.trace_path))
    try:
        if run.package.reset_caches is not None:
            run.package.reset_caches()
        with observability.collecting(sink), SessionLocal() as session:
            use_case = PreviewEvaluation(
                instruments=DesignInstrumentGateway(session),
                profiles=ProfilingGateway(session),
                coverage=run.package.coverage,
                executors=with_progress(run.package.executors, run.record_step),
            )
            preview = use_case(run.command)
    except ProfileNotAvailable as exc:
        run.finish(error=RunError("profile_missing", str(exc)))
    except InstrumentNotEvaluable as exc:
        run.finish(error=RunError("instrument_missing", str(exc)))
    except AssessorExecutionError as exc:
        # ADR-0037 §3: below the failure budget the derivation absorbed the failures as
        # execution_error outcomes (the run ends `done`, its failed steps `ok=False`), so
        # reaching here means the budget was exceeded and the run was not an evaluation.
        # Nothing was persisted — running it again IS the retry.
        run.finish(error=RunError("assessor_failed", str(exc)))
    except Exception as exc:  # noqa: BLE001 — a worker thread has nowhere to raise
        logger.exception("preview run %s failed unexpectedly", run.run_id)
        run.finish(error=RunError("unexpected", f"{type(exc).__name__}: {exc}"))
    else:
        run.finish(preview=preview)


# One registry per process, like the event dispatcher. The API reads it; nothing else does.
preview_runs = PreviewRunRegistry()
