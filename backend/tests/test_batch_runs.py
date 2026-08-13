"""What a batch does between courses — with the evaluation itself faked out.

`EvaluateContent` already has its own tests, and ADR-0037 already decides what happens
INSIDE one evaluation. What is pinned here is the layer above it: which failures are one
course's problem and which are everyone's, that stopping stops, and that what already
succeeded is neither redone nor undone.
"""

import threading
import time
from uuid import uuid4

import pytest

from app.modules.evaluation.application.evaluate_content import ProfileNotAvailable
from app.modules.evaluation.domain.model import Coverage, InvalidAutomatedEvaluation
from app.modules.evaluation.infrastructure.assessors import AssessorPackage
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.modules.evaluation_studies.application.dtos import ContentInfo
from app.platform import batch_runs as module
from app.platform.batch_runs import BatchRun, execute


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


def course(name: str) -> ContentInfo:
    return ContentInfo(
        content_id=uuid4(),
        external_id=name,
        package_format="LearnpackV2",
        brief_id=uuid4(),
        generator_version_id=None,
    )


def a_run(courses, workers: int = 1, already=(), study_id=None) -> BatchRun:
    return BatchRun(
        run_id=uuid4(),
        study_id=study_id or uuid4(),
        instrument_version_id="qa-v6",
        assessor_id=uuid4(),
        package=package(),
        courses=courses,
        already_evaluated=already,
        workers=workers,
    )


def answering(monkeypatch, answers: dict[str, object]):
    """Replace the use case with a script keyed by course name; record what it was asked."""
    asked: list[str] = []

    def fake(run: BatchRun, content: ContentInfo):
        asked.append(content.external_id)
        answer = answers.get(content.external_id)
        if isinstance(answer, BaseException):
            raise answer
        return uuid4()

    monkeypatch.setattr(module, "_run_use_case", fake)
    return asked


def statuses(run: BatchRun) -> dict[str, str]:
    return {o.external_id: o.status for o in run.view().outcomes}


# ------------------------------------------------------------------ the ordinary case


def test_every_course_is_evaluated_and_named(monkeypatch):
    courses = [course("a"), course("b"), course("c")]
    asked = answering(monkeypatch, {})
    run = a_run(courses)

    execute(run)

    view = run.view()
    assert view.status == "done"
    assert asked == ["a", "b", "c"]
    assert view.evaluated == 3 and view.done == view.total == 3
    assert all(o.evaluation_id is not None for o in view.outcomes)


def test_courses_run_in_parallel_up_to_the_worker_count(monkeypatch):
    """The workers decide how many courses are open; how many REQUESTS are in flight is the
    transport's ceiling, one level down, which is what keeps the two from multiplying."""
    lock = threading.Lock()
    in_flight = 0
    high_water = 0

    def fake(run, content):
        nonlocal in_flight, high_water
        with lock:
            in_flight += 1
            high_water = max(high_water, in_flight)
        time.sleep(0.02)
        with lock:
            in_flight -= 1
        return uuid4()

    monkeypatch.setattr(module, "_run_use_case", fake)
    run = a_run([course(f"c{i}") for i in range(6)], workers=3)

    execute(run)

    assert high_water == 3
    assert run.view().evaluated == 6


def test_what_was_already_evaluated_is_skipped_not_repeated(monkeypatch):
    """Resuming a batch that died halfway is running it again — the expensive half is what
    it does NOT do."""
    first, second = course("a"), course("b")
    asked = answering(monkeypatch, {})
    run = a_run([first, second], already=[first.content_id])

    execute(run)

    assert asked == ["b"]
    assert statuses(run) == {"a": "skipped", "b": "evaluated"}
    assert run.view().done == 2  # a skipped course is a decided course


# ------------------------------------------------------------------ whose failure it is


def test_one_courses_own_failure_does_not_stop_the_others(monkeypatch):
    asked = answering(monkeypatch, {"b": ProfileNotAvailable("content b has no ok profile")})
    run = a_run([course("a"), course("b"), course("c")])

    execute(run)

    assert asked == ["a", "b", "c"]
    assert statuses(run) == {"a": "evaluated", "b": "failed", "c": "evaluated"}
    assert run.view().status == "done"
    assert "no ok profile" in next(o.cause for o in run.view().outcomes if o.external_id == "b")


def test_a_configuration_failure_ends_the_batch_on_the_first_course(monkeypatch):
    """It is the wiring, not the course: proving it nineteen more times costs nineteen
    courses' worth of latency to learn what the first one already said."""
    asked = answering(
        monkeypatch,
        {"a": AssessorExecutionError("no LLM API key configured", kind="configuration")},
    )
    run = a_run([course("a"), course("b"), course("c")])

    execute(run)

    assert asked == ["a"]
    assert statuses(run) == {"a": "failed", "b": "cancelled", "c": "cancelled"}


def test_a_coverage_bug_ends_the_batch_too(monkeypatch):
    asked = answering(
        monkeypatch, {"a": InvalidAutomatedEvaluation("the assessor maps no executor for cr-x")}
    )
    run = a_run([course("a"), course("b")])

    execute(run)

    assert asked == ["a"]
    assert statuses(run)["b"] == "cancelled"


def test_three_transport_failures_in_a_row_end_the_batch(monkeypatch):
    down = AssessorExecutionError("transport retry budget exhausted", kind="transport")
    asked = answering(monkeypatch, {"a": down, "b": down, "c": down})
    run = a_run([course("a"), course("b"), course("c"), course("d")])

    execute(run)

    assert asked == ["a", "b", "c"]  # the fourth is never attempted
    assert statuses(run)["d"] == "cancelled"


def test_a_recovered_endpoint_resets_the_streak(monkeypatch):
    """Two failures and a success is a flaky network, not an outage."""
    down = AssessorExecutionError("transport retry budget exhausted", kind="transport")
    asked = answering(monkeypatch, {"a": down, "b": down, "d": down})
    run = a_run([course("a"), course("b"), course("c"), course("d")])

    execute(run)

    assert asked == ["a", "b", "c", "d"]
    assert run.view().status == "done"


# ------------------------------------------------------------------ stopping


def test_cancelling_stops_starting_and_keeps_what_finished(monkeypatch):
    """Nothing is undone because nothing needs undoing: each course is its own transaction
    and an evaluation that does not reach its end persists nothing (ADR-0037)."""
    courses = [course("a"), course("b"), course("c")]
    asked: list[str] = []

    def fake(run, content):
        asked.append(content.external_id)
        if content.external_id == "a":
            run.cancel()  # as an operator or an HTTP handler would, mid-flight
        return uuid4()

    monkeypatch.setattr(module, "_run_use_case", fake)
    run = a_run(courses)

    execute(run)

    view = run.view()
    assert asked == ["a"]
    assert statuses(run) == {"a": "evaluated", "b": "cancelled", "c": "cancelled"}
    assert view.status == "cancelled"
    assert view.evaluated == 1  # what finished, stays


# ------------------------------------------------------------------ what a reader sees


def test_progress_and_the_estimate_come_from_what_this_run_measured(monkeypatch):
    answering(monkeypatch, {})
    run = a_run([course(f"c{i}") for i in range(4)])
    assert run.view().remaining_ms_estimate is None  # nothing measured yet, nothing promised

    execute(run)

    view = run.view()
    assert (view.done, view.total, view.pending) == (4, 4, 0)
    assert view.remaining_ms_estimate is None  # nothing left to estimate either
    # One step per course, in the order they were decided.
    assert [step.label for step in view.steps] == ["c0", "c1", "c2", "c3"]


def test_a_run_that_dies_unexpectedly_ends_refused_rather_than_hanging(monkeypatch):
    def explode(run, content):
        raise RuntimeError("something nobody predicted")

    monkeypatch.setattr(module, "_run_use_case", explode)
    run = a_run([course("a")])

    execute(run)

    view = run.view()
    assert view.status == "refused"
    assert view.error is not None and "something nobody predicted" in view.error


# ------------------------------------------------------------------ the registry


def registry() -> module.BatchRunRegistry:
    return module.BatchRunRegistry(keep=3)


def test_a_started_run_is_remembered_and_readable(monkeypatch):
    """Started, not awaited: the caller gets an id back and reads the run afterwards."""
    finished = threading.Event()

    def fake(run, content):
        finished.wait(timeout=5)
        return uuid4()

    monkeypatch.setattr(module, "_run_use_case", fake)
    runs = registry()
    run = runs.start(a_run([course("a")]))

    assert runs.get(run.run_id) is run
    assert runs.get(run.run_id).view().status == "running"
    finished.set()


def test_a_run_that_would_overlap_a_running_one_is_refused(monkeypatch):
    """Two batches over one course decide by arrival order, since every reader takes the
    most recent judgment. Refusing is cheaper than explaining."""
    holding = threading.Event()
    monkeypatch.setattr(module, "_run_use_case", lambda run, content: holding.wait(timeout=5))
    shared = course("a")
    runs = registry()
    runs.start(a_run([shared, course("b")]))

    with pytest.raises(module.BatchRefused) as refused:
        runs.start(a_run([shared, course("c")]))

    assert refused.value.kind == "overlapping_run"
    holding.set()


def test_batches_over_different_courses_run_together(monkeypatch):
    """The guard is about the same course, not about batches: two studies with nothing in
    common are two independent runs, and how many requests that puts in flight is the
    transport's ceiling, not this registry's business."""
    holding = threading.Event()
    monkeypatch.setattr(module, "_run_use_case", lambda run, content: holding.wait(timeout=5))
    runs = registry()

    first = runs.start(a_run([course("a")]))
    second = runs.start(a_run([course("b")]))

    assert {first.run_id, second.run_id} <= set(runs._runs)
    holding.set()


def test_a_finished_run_is_forgotten_before_one_still_running(monkeypatch):
    """The oldest goes, but never the one whose thread is still reporting into it — which
    is also the one somebody is watching."""
    holding = threading.Event()

    def fake(run, content):
        if content.external_id == "held":
            holding.wait(timeout=5)
        return uuid4()

    monkeypatch.setattr(module, "_run_use_case", fake)
    runs = module.BatchRunRegistry(keep=2)
    running = runs.start(a_run([course("held")]))
    older = runs.start(a_run([course("b")]))
    while older.view().status == "running":
        time.sleep(0.01)

    newest = runs.start(a_run([course("c")]))

    assert runs.get(older.run_id) is None  # the ended one made room
    assert runs.get(running.run_id) is running  # still working, never forgotten
    assert runs.get(newest.run_id) is newest
    holding.set()


def test_a_studys_runs_come_back_newest_first(monkeypatch):
    monkeypatch.setattr(module, "_run_use_case", lambda run, content: uuid4())
    runs = registry()
    study = uuid4()
    first = runs.start(a_run([course("a")], study_id=study))
    second = runs.start(a_run([course("b")], study_id=study))
    runs.start(a_run([course("c")]))  # another study's

    assert [r.run_id for r in runs.for_study(study)] == [second.run_id, first.run_id]
