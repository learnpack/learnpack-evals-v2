"""What the LLM transport did, as a stream anyone can listen to.

One record per ATTEMPT — not per successful call: a retry that never produced a usable
answer is exactly the thing worth looking at, and a run that failed has nothing else to
show for itself. Each record carries what was sent (the messages, verbatim), what came
back (the raw text, the finish reason, the provider that answered) and what it cost.

Listening is opt-in and scoped: `collecting(sink)` installs a sink for the current
context, `emit` is a no-op when nobody is listening. The transport therefore calls `emit`
unconditionally and stays ignorant of who — if anyone — is on the other end. The same
stream feeds live progress and the post-mortem trace file; they are the same events read
at different moments.

Observing never changes the observed: a sink that raises is logged and swallowed, because
a broken listener must not turn a working evaluation into a failed one. For the same
reason nothing here re-versions an assessor (ADR-0034 §1): recording an answer does not
change which answer arrives.
"""

import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmCall:
    """One attempt at one LLM call, from the transport's point of view."""

    task_id: str | None
    attempt: int
    model_requested: str
    messages: tuple[Mapping[str, str], ...]
    latency_ms: int
    model_answered: str | None = None
    # Which upstream provider served the request. OpenRouter routes one model id to
    # several of them, and they do not honor `response_format` alike — so "who answered"
    # is the difference between two runs that ask the same question and get different
    # shapes back.
    provider: str | None = None
    response_text: str | None = None
    finish_reason: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_record(self) -> dict[str, Any]:
        """The JSON-ready shape written to the trace file and served to the page."""
        return {
            "task_id": self.task_id,
            "attempt": self.attempt,
            "model_requested": self.model_requested,
            "model_answered": self.model_answered,
            "provider": self.provider,
            "messages": [dict(message) for message in self.messages],
            "response_text": self.response_text,
            "finish_reason": self.finish_reason,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


Sink = Callable[[LlmCall], None]

_sink: ContextVar[Sink | None] = ContextVar("llm_call_sink", default=None)


def emit(call: LlmCall) -> None:
    """Hand a record to whoever is listening in this context; do nothing if nobody is."""
    sink = _sink.get()
    if sink is None:
        return
    try:
        sink(call)
    except Exception:  # noqa: BLE001 — a broken listener must not fail the evaluation
        logger.exception("an LLM call sink raised; the call itself is unaffected")


@contextmanager
def collecting(sink: Sink) -> Iterator[None]:
    """Listen to every LLM call made in this context (this thread's, for a job runner)."""
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)


def recording() -> tuple[list[LlmCall], Sink]:
    """A list and the sink that fills it — the sink most callers want."""
    calls: list[LlmCall] = []
    return calls, calls.append


def messages_of(messages: Sequence[Mapping[str, str]]) -> tuple[Mapping[str, str], ...]:
    """A snapshot of the conversation as sent: the caller keeps mutating its own list."""
    return tuple(dict(message) for message in messages)
