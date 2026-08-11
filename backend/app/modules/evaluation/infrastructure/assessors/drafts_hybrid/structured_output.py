"""Structured output with feedback retry — the pattern under every semantic task.

One call shape: ask for JSON, parse it, validate it against the task's contract, and when
the model missed, ask again WITH the validator's feedback in the conversation — the model
sees its own answer and what was wrong with it. When the schema budget is spent, or the
transport's own retry budget under this call is spent, the task raises
`AssessorExecutionError` and the evaluation aborts whole (ADR-0034 clause 4).

Grounding is part of validation on purpose: a task whose contract says "verbatim" hands a
validator that checks the quote against the source, so a hallucinated citation is a schema
violation like any other — fed back once, fatal when persistent. Evidence that cannot be
verified is not evidence (ADR-0009).

This module is duplicated per LLM-carrying assessor, not shared (ADR-0034 clause 5): the
retry budget and the feedback wording shape what the judge finally answers, so they are
identity. Editing this file is a new version of `drafts-hybrid`.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.platform.llm import ChatCompletionsClient, LlmError

# First ask + two feedback rounds. Past that, the model is not going to start complying,
# and every extra round is paid latency in front of a fixed answer.
MAX_SCHEMA_ATTEMPTS = 3

# A validator returns the contract violations it found — empty means the payload holds.
Validator = Callable[[Any], list[str]]


@dataclass(frozen=True)
class LlmUsage:
    """What one task actually spent — reported as a `ComputedMetric` with the evaluation."""

    model: str
    calls: int
    tokens_in: int
    tokens_out: int
    latency_ms: int


def request_structured_output(
    client: ChatCompletionsClient,
    *,
    task_id: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    validate: Validator,
    temperature: float,
    max_tokens: int,
) -> tuple[Any, LlmUsage]:
    """One validated JSON payload, or `AssessorExecutionError` — never a half answer."""
    messages: list[Mapping[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    calls = tokens_in = tokens_out = latency_ms = 0
    model_used = model
    violations: list[str] = []
    for _ in range(MAX_SCHEMA_ATTEMPTS):
        try:
            completion = client.complete(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                # Names this question in the trace and nothing else — it never reaches the
                # wire, so it is not part of what the judge is asked (ADR-0034 §5).
                task_id=task_id,
            )
        except LlmError as exc:
            raise AssessorExecutionError(f"task '{task_id}': {exc}") from exc
        calls += 1
        tokens_in += completion.tokens_in
        tokens_out += completion.tokens_out
        latency_ms += completion.latency_ms
        model_used = completion.model

        payload, parse_error = _parse_json(completion.text)
        violations = [parse_error] if parse_error else validate(payload)
        if not violations:
            return payload, LlmUsage(
                model=model_used,
                calls=calls,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
            )
        messages = [
            *messages,
            {"role": "assistant", "content": completion.text},
            {"role": "user", "content": _feedback(violations)},
        ]
    raise AssessorExecutionError(
        f"task '{task_id}': the model never satisfied the output contract in "
        f"{MAX_SCHEMA_ATTEMPTS} attempts (last violations: {'; '.join(violations)})"
    )


def _parse_json(text: str) -> tuple[Any, str | None]:
    """The payload, or the violation to feed back. Tolerates one markdown fence — models
    wrap JSON in one often enough that failing on it would spend a retry on cosmetics."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1] if "\n" in candidate else ""
        candidate = candidate.rsplit("```", 1)[0].strip()
    try:
        return json.loads(candidate), None
    except ValueError as exc:
        return None, f"the answer is not valid JSON ({exc})"


def _feedback(violations: Sequence[str]) -> str:
    listed = "\n".join(f"- {violation}" for violation in violations)
    return (
        "Your previous answer violates the required output contract:\n"
        f"{listed}\n"
        "Answer again with a single JSON object that satisfies the contract exactly. "
        "Do not apologize, do not explain — the JSON object only."
    )
