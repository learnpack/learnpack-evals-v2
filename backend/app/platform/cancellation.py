"""Stopping long, expensive work — as a scope, the way listening is one.

An evaluation is minutes of LLM calls and real money. Whoever started one must be able to
stop it, and stopping has to mean *soon*: a run that finishes its last fifteen calls before
noticing has not obeyed. So the check lives where every call passes — the transport, before
it emits — and it reaches there the same way a trace sink does, through a `ContextVar`
(`app.platform.observability`). The transport asks whether it may proceed; it never learns
who is asking or what a batch is.

**Cancelling is control flow, not a failure.** `Cancelled` therefore derives from
`BaseException`, for the same reason `KeyboardInterrupt` does: nothing on the path may
absorb it into an error state. An assessor that caught it as an execution failure would
turn a stopped run into a persisted evaluation full of `execution_error` — a record of a
judgment nobody made. The one place that catches it does so by name.

What cancelling does NOT do is undo. The unit of work is one evaluation, each in its own
transaction, and an evaluation that does not reach its end persists nothing (ADR-0037).
Stopping therefore means *stop starting*: what finished stays finished, what was in flight
leaves no trace, and nothing needs rolling back.

A `ContextVar` and not a thread-local so a worker gets a token by entering the scope
itself: a new thread starts with an empty context, which is what makes "this run's token"
mean this run's, however many runs share the process.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar


class Cancelled(BaseException):
    """The work was asked to stop. Never an error, never caught by accident."""


class CancellationToken:
    """A flag one side sets and the other reads. Deliberately not much more than that.

    Thread-safe by being a single boolean guarded by an event: the setter is whoever holds
    the run (an HTTP handler, a signal handler), the readers are every worker thread.
    """

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def check(self) -> None:
        if self._cancelled.is_set():
            raise Cancelled("the run was cancelled")


_token: ContextVar[CancellationToken | None] = ContextVar("cancellation_token", default=None)


@contextmanager
def cancel_scope(token: CancellationToken) -> Iterator[None]:
    """Everything done in this context answers to `token` (this thread's context)."""
    handle = _token.set(token)
    try:
        yield
    finally:
        _token.reset(handle)


def check() -> None:
    """Raise `Cancelled` if the current context was cancelled; do nothing otherwise.

    Called before work worth not doing. Outside any scope this is a no-op, which is what
    keeps every existing caller — the CLI, a single evaluation, a dry run — unaware that
    cancellation exists at all.
    """
    token = _token.get()
    if token is not None:
        token.check()
