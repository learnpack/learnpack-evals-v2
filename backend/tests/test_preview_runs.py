"""The dry-run's job machinery, without a database in the way.

What is pinned here is what the page depends on and the API tests cannot reach cheaply:
a run reports every executor as it lands, an LLM attempt reads as progress, a worker
thread never dies silently, the registry forgets the oldest run rather than the one you
are looking at, and the same records that drive the live view end up whole in the trace
file.
"""

import json
import time
from types import SimpleNamespace
from uuid import uuid4

from app.modules.evaluation.application.preview_evaluation import PreviewEvaluationCommand
from app.modules.evaluation.domain.model import Coverage, ExecutorResult
from app.modules.evaluation.infrastructure import preview_runs as module
from app.modules.evaluation.infrastructure.assessors import AssessorPackage
from app.modules.evaluation.infrastructure.preview_runs import (
    PreviewRun,
    PreviewRunRegistry,
    RunStep,
    execute,
    with_progress,
)
from app.platform import observability


def package(**overrides) -> AssessorPackage:
    defaults = {
        "name": "fake",
        "version": "1",
        "instrument_id": "some-lineage",
        "executors": {},
        "coverage": Coverage(executes=frozenset(), abstains={}),
        "source_config": {},
    }
    return AssessorPackage(**{**defaults, **overrides})


def a_run(**overrides) -> PreviewRun:
    return PreviewRun(
        run_id=uuid4(),
        package=package(**overrides.pop("package", {})),
        command=PreviewEvaluationCommand(content_id=uuid4(), instrument_version_id="v1"),
    )


# ------------------------------------------------------------------ executors as progress


def test_an_executor_reports_its_verdict_without_changing_it():
    reported: list[RunStep] = []
    passing = ExecutorResult(passed=True, quote="q", locator=None, failure_mode=None, metrics=())
    failing = ExecutorResult(passed=False, quote="q", locator=None, failure_mode="m", metrics=())

    wrapped = with_progress(
        {"cr-a": lambda spec, profile: passing, "cr-b": lambda spec, profile: failing},
        reported.append,
    )

    assert wrapped["cr-a"](None, None) is passing  # the verdict travels untouched
    assert wrapped["cr-b"](None, None) is failing
    assert [(s.label, s.detail, s.ok) for s in reported] == [
        ("cr-a", "pass", True),
        # A `fail` is a verdict, not a malfunction: the step is fine, the criterion is not.
        ("cr-b", "fail", True),
    ]


def test_an_executor_that_blows_up_is_reported_and_still_raises():
    reported: list[RunStep] = []

    def boom(spec, profile):
        raise RuntimeError("the model said no")

    wrapped = with_progress({"cr-a": boom}, reported.append)

    try:
        wrapped["cr-a"](None, None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("the failure must reach the derivation, not stop at the log")
    assert not reported[0].ok and "the model said no" in reported[0].detail


# ------------------------------------------------------------------- LLM calls as progress


def a_call(**overrides) -> observability.LlmCall:
    defaults = {
        "task_id": "outcomes_extraction",
        "attempt": 1,
        "model_requested": "vendor/model",
        "messages": ({"role": "user", "content": "hi"},),
        "latency_ms": 40,
        "tokens_in": 900,
        "tokens_out": 30,
    }
    return observability.LlmCall(**{**defaults, **overrides})


def test_an_attempt_reads_as_progress_and_is_kept_whole():
    run = a_run()

    run.record_call(a_call())

    view = run.view()
    (step,) = view.steps
    assert step.kind == "llm_call" and step.label == "outcomes_extraction"
    assert step.detail == "attempt 1 · 900→30 tokens" and step.ok
    assert view.calls[0].messages[0]["content"] == "hi"  # the trace keeps the whole thing


def test_a_truncated_answer_says_so_in_the_progress_line():
    """`length` reaches the caller as "the answer is not valid JSON" — the step is where
    the actual cause is legible."""
    run = a_run()

    run.record_call(a_call(finish_reason="length"))

    assert "finish_reason=length" in run.view().steps[0].detail


def test_a_failed_attempt_carries_its_error():
    run = a_run()

    run.record_call(a_call(attempt=2, error="HTTP 429", tokens_in=0, tokens_out=0))

    step = run.view().steps[0]
    assert step.detail == "attempt 2 · HTTP 429" and not step.ok


# --------------------------------------------------------------------------- the registry


def test_the_oldest_run_is_forgotten_first(monkeypatch):
    """Bounded on purpose — prompts and raw answers live in memory. What you just ran is
    what must survive."""
    monkeypatch.setattr(module, "execute", lambda run: run.finish())
    registry = PreviewRunRegistry(keep=2)
    command = PreviewEvaluationCommand(content_id=uuid4(), instrument_version_id="v1")

    first, second, third = (registry.start(package(), command) for _ in range(3))

    assert registry.get(first.run_id) is None
    assert registry.get(second.run_id) is not None
    assert registry.get(third.run_id) is not None


def test_a_worker_never_dies_silently():
    """A thread has nowhere to raise: an unhandled failure must end the run, not leave the
    page polling forever."""

    def explode() -> None:
        raise RuntimeError("something nobody predicted")

    run = a_run(package={"reset_caches": explode})

    execute(run)

    view = run.view()
    assert view.status == "failed" and view.error is not None
    assert view.error.kind == "unexpected"
    assert "something nobody predicted" in view.error.message


# --------------------------------------------------------------------------- the trace file


def test_a_trace_file_is_written_only_where_a_machine_asked_for_one(monkeypatch, tmp_path):
    """`LLM_TRACE_DIR` empty means off: a deployment that should not be writing prompts
    to disk opts out by never setting it."""
    monkeypatch.setattr(observability, "get_settings", lambda: SimpleNamespace(llm_trace_dir=""))
    assert observability.trace_path("a-run") is None

    monkeypatch.setattr(
        observability, "get_settings", lambda: SimpleNamespace(llm_trace_dir=str(tmp_path))
    )
    assert observability.trace_path("a-run") == tmp_path / "a-run.jsonl"


def test_each_attempt_is_one_json_line_kept_whole(tmp_path):
    path = tmp_path / "run.jsonl"
    sink = observability.jsonl_sink(path)

    sink(a_call())
    sink(a_call(attempt=2, error="HTTP 429"))

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [record["attempt"] for record in records] == [1, 2]
    assert records[0]["messages"] == [{"role": "user", "content": "hi"}]
    assert records[1]["error"] == "HTTP 429"


def test_one_stream_feeds_both_the_live_run_and_the_file(tmp_path):
    """Progress and trace are the same records, read at different moments."""
    run = a_run()
    path = tmp_path / "run.jsonl"

    observability.fan_out(run.record_call, observability.jsonl_sink(path))(a_call())

    assert len(run.view().calls) == 1
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_the_clock_runs_while_the_run_does_and_stops_when_it_ends():
    """Elapsed time is measured on the server: the page never has to reconcile two
    clocks, and a finished run does not keep aging on screen."""
    run = a_run()
    time.sleep(0.02)
    assert run.view().elapsed_ms > 0

    run.finish()
    frozen = run.view().elapsed_ms
    time.sleep(0.02)
    assert run.view().elapsed_ms == frozen
