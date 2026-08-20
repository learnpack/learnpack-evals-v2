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

**Once means once even when two criteria ask together.** The derivation may run its criteria
concurrently (ADR-0048), and "look it up, and run it if it is missing" is two steps: two
criteria sharing a task both found it missing and both paid. So an entry is claimed before
the work starts and the others wait on it. That is still the same rule this module always
had — the same question asked once — restated for callers that arrive at the same moment.
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from app.modules.evaluation.domain.model import ExecutionFailure, ProfileData

Key = tuple[str, UUID]


class _Claim:
    """One question, claimed by whoever got there first; the rest wait for its answer.

    `failed` is separate from `error` because the two failures are remembered differently:
    an `ExecutionFailure` is the answer (criteria sharing a task degrade together with one
    cause, ADR-0037 §2) while anything else is a bug that must reach every caller and be
    cached for none — so the waiters have to be able to tell "it failed, ask again yourself"
    from "here is the failure".
    """

    __slots__ = ("answered", "error", "failed", "value")

    def __init__(self) -> None:
        self.answered = threading.Event()
        self.value: Any = None
        self.error: ExecutionFailure | None = None
        self.failed = False


class TaskMemo:
    """One namespace of memoized answers, scoped to the current context."""

    def __init__(self, name: str) -> None:
        self._entries: ContextVar[dict[Key, _Claim]] = ContextVar(name)
        # Guards the claim itself — deciding who runs — and nothing else. The work happens
        # outside it, so one slow question never blocks a different one.
        self._claiming = threading.Lock()

    def _current(self) -> dict[Key, _Claim]:
        try:
            return self._entries.get()
        except LookupError:
            # First use in this context — a fresh thread, or a caller that never opened a
            # scope. Either way these entries are this context's and nobody else's.
            fresh: dict[Key, _Claim] = {}
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
        while True:
            entries = self._current()
            with self._claiming:
                claim = entries.get(key)
                mine = claim is None
                if claim is None:
                    claim = _Claim()
                    entries[key] = claim

            if mine:
                try:
                    claim.value = run()
                except ExecutionFailure as exc:
                    claim.error = exc
                except BaseException:
                    # Not an answer and not a fact of this run: drop the claim so nobody
                    # inherits it, and let it reach this caller as it always did.
                    claim.failed = True
                    with self._claiming:
                        if entries.get(key) is claim:
                            del entries[key]
                    raise
                finally:
                    claim.answered.set()
            else:
                claim.answered.wait()
                if claim.failed:
                    # Whoever ran hit a bug. It is not cached, so this caller asks for
                    # itself and meets the same bug — which is the point of not caching it.
                    continue

            if claim.error is not None:
                raise claim.error
            return claim.value
