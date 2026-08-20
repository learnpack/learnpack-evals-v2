"""The mechanism the derivation delegates to (ADR-0048).

Three properties, and the module is worth nothing without any of them: the work happens at
once, the answers come back in the caller's order however they finished, and each worker runs
inside the caller's context — which is what carries a run's memoized answers, its trace sink
and its cancellation token into a thread that would otherwise start with none.

Concurrency is pinned with a barrier rather than a stopwatch: every item waits for all of
them, so a sequential implementation cannot clear the first and there is no timing threshold
to tune on a slow machine.
"""

import threading
import time
from contextvars import ContextVar

import pytest

from app.platform.concurrency import all_at_once


def test_the_work_happens_at_once():
    barrier = threading.Barrier(4, timeout=20)

    def work(item: int) -> int:
        barrier.wait()
        return item * 2

    assert list(all_at_once(work, [1, 2, 3, 4])) == [2, 4, 6, 8]


def test_the_answers_come_back_in_the_callers_order():
    """What finished first is not something a caller can observe, so the slowest item first
    and the fastest last still answer in the order they were given."""
    started = threading.Barrier(3, timeout=20)

    def work(item: int) -> int:
        started.wait()  # nobody returns before everybody has begun
        time.sleep(0.05 * (3 - item))  # the first item is the slowest
        return item

    assert list(all_at_once(work, [1, 2, 3])) == [1, 2, 3]


def test_each_worker_runs_inside_the_callers_context():
    """The reason this module exists rather than a bare `pool.map`: a fresh thread starts
    with an empty context, and everything a run carries travels in `ContextVar`s."""
    carried: ContextVar[str] = ContextVar("carried")
    carried.set("the caller's")

    assert list(all_at_once(lambda _: carried.get("lost"), [1, 2, 3])) == ["the caller's"] * 3


def test_one_item_needs_no_thread_at_all():
    """The degenerate case stays on the calling thread, so nothing pays for a pool to do one
    thing — and a `ContextVar` set INSIDE the work is still visible to the caller, which a
    worker's copied context would have swallowed."""
    where: ContextVar[str] = ContextVar("where")

    def work(item: int) -> int:
        where.set("the calling thread")
        return item

    assert list(all_at_once(work, [7])) == [7]
    assert where.get("somewhere else") == "the calling thread"


def test_what_the_work_raises_reaches_the_caller():
    def work(item: int) -> int:
        if item == 2:
            raise ValueError("the second one")
        return item

    with pytest.raises(ValueError, match="the second one"):
        all_at_once(work, [1, 2, 3])
