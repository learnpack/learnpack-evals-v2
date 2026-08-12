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

import json
import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmCall:
    """One attempt at one LLM call, from the transport's point of view."""

    task_id: str | None
    attempt: int
    model_requested: str
    messages: tuple[Mapping[str, str], ...]
    latency_ms: int
    # What was asked for besides the conversation: temperature, the output budget, the
    # response format, whatever else the caller pinned. Sampling decides the answer as
    # much as the prompt does — a trace without it cannot tell a bad prompt from a badly
    # sampled model, which is exactly the question that took four runs to settle once.
    sampling: Mapping[str, Any] = field(default_factory=dict)
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
            "sampling": dict(self.sampling),
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


def fan_out(*sinks: Sink) -> Sink:
    """One stream, several listeners — live progress and the file, from the same records."""

    def deliver(call: LlmCall) -> None:
        for sink in sinks:
            sink(call)

    return deliver


# --------------------------------------------------------------------------- the file
#
# What outlives the process. Runs are kept in memory and only the last few, so the file
# is where a calibration attempt from yesterday can still be compared against today's.


def trace_path(name: str) -> Path | None:
    """Where this run's trace goes, or None when nobody asked for one.

    `LLM_TRACE_DIR` empty means off — the setting is how a machine opts in, so a
    deployment that should not be writing prompts to disk simply never sets it.
    """
    directory = get_settings().llm_trace_dir.strip()
    if not directory:
        return None
    try:
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.exception(
            "LLM_TRACE_DIR %r cannot be used; this run leaves no trace file", directory
        )
        return None
    return root / f"{name}.jsonl"


def jsonl_sink(path: Path) -> Sink:
    """Append one JSON object per attempt, flushed as it happens.

    Reopened per record on purpose: a run that dies mid-way is exactly the one whose
    trace has to be readable, and there is no volume here worth buffering for.
    """

    def write(call: LlmCall) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(call.as_record(), ensure_ascii=False) + "\n")

    return write
