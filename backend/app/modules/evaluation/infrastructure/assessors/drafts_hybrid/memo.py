"""What this assessor remembers while it evaluates one content, and never longer.

Several criteria deliberately read one answer: the instrument writes them as separate
criteria over the same datum, profiles are immutable, and paying twice for one question
would be waste. Typed failures are remembered the same way, so criteria sharing a task
degrade together with one cause instead of re-asking a question that just degenerated
(ADR-0037 §2).

**The scope of that memory is one evaluation.** It used to be one process: a dict at module
level, emptied at the start of each dry run. That works while runs never overlap, and stops
working the moment they do — one run's reset empties another's answers, and over the same
profile one run can be served the other's answer, which quietly stops two repeats from
being two samples. Repeats of one content are how a judge's variance is measured at all, so
"quietly" is the expensive part.

A `ContextVar` fixes both halves at once. A thread that never entered a scope gets its own
entries on first use — a new thread starts with an empty context — so workers evaluating
different contents in parallel cannot share anything by accident. And `scope()` gives
isolation between sequential runs in one thread, which is what a dry run needs and what it
used to get by clearing a global.

Within one evaluation nothing changes: the same questions are asked once and shared exactly
as before. This is not identity (ADR-0034) — it changes what a run SPENDS and what it
leaks, never which answer it gets.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from app.modules.evaluation.domain.model import ExecutionFailure, ProfileData

Key = tuple[str, UUID]


class TaskMemo:
    """One namespace of memoized answers, scoped to the current context."""

    def __init__(self, name: str) -> None:
        self._entries: ContextVar[dict[Key, Any]] = ContextVar(name)

    def _current(self) -> dict[Key, Any]:
        try:
            return self._entries.get()
        except LookupError:
            # First use in this context — a fresh thread, or a caller that never opened a
            # scope. Either way these entries are this context's and nobody else's.
            fresh: dict[Key, Any] = {}
            self._entries.set(fresh)
            return fresh

    @contextmanager
    def scope(self) -> Iterator[None]:
        """Everything memoized inside is forgotten on the way out."""
        handle = self._entries.set({})
        try:
            yield
        finally:
            self._entries.reset(handle)

    def clear(self) -> None:
        self._current().clear()

    def memoized(self, task_id: str, profile: ProfileData, run: Callable[[], Any]) -> Any:
        """Whatever `run` returns, once per (task, profile) in this context.

        Only `ExecutionFailure` is remembered as a failure; a bug propagates every time,
        because caching one would hide it behind the first criterion that hit it.
        """
        key = (task_id, profile.profile_id)
        entries = self._current()
        if key not in entries:
            try:
                entries[key] = run()
            except ExecutionFailure as exc:
                entries[key] = exc
                raise
        remembered = entries[key]
        if isinstance(remembered, ExecutionFailure):
            raise remembered
        return remembered
