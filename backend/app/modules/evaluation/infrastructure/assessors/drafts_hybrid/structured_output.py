"""Structured output with feedback retry — the pattern under every semantic task.

One call shape: ask for JSON, parse it, validate it against the task's contract, and when
the model missed, ask again WITH the validator's feedback in the conversation — the model
sees its own answer and what was wrong with it. Feedback works when the answer is a fixable
mistake; it is useless against **degeneration** (a reply repeated verbatim), where feeding
the broken answer back puts the loop *in* the context. So the two failure shapes get two
remedies (ADR-0037 §7): a contract violation keeps the feedback retry; a degeneration and
an unusable answer cut at the token budget each buy **one retry on a clean conversation**
— `messages` rebuilt from scratch, nothing of the broken round carried over — and a second
identical failure is the poison case and raises. The budget kind joined in v8 on field
evidence: capped runaways are stochastic per REQUEST, strongly provider-correlated (every
one of the campaign's came from one upstream that mostly answers fine), so a fresh
conversation re-rolls the serving itself — the first field save landed on the same
provider and succeeded. Transport and configuration are never clean-retried: transport
has its own backoff under this call, and configuration is deterministic everywhere.

Every raise carries a machine-readable `kind` (plumbing, not identity — `errors.py`), so
the derivation can record *why* a criterion could not be judged and the retry policy can
read the difference instead of parsing prose.

Grounding is part of validation on purpose: a task whose contract says "verbatim" hands a
validator that checks the quote against the source, so a hallucinated citation is a schema
violation like any other — fed back once, fatal when persistent. Evidence that cannot be
verified is not evidence (ADR-0009).

This module is duplicated per LLM-carrying assessor, not shared (ADR-0034 clause 5): the
retry budgets and the feedback wording shape what the judge finally answers, so they are
identity. Editing this file is a new version of `drafts-hybrid`.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.platform.llm import (
    ChatCompletionsClient,
    LlmConfigurationError,
    LlmError,
    LlmTransportError,
)

# First ask + two feedback rounds. Past that, the model is not going to start complying,
# and every extra round is paid latency in front of a fixed answer.
MAX_SCHEMA_ATTEMPTS = 3

# Fresh-conversation retries, for the two failure shapes a re-roll can dissolve. One: the
# first retry is the cheap bet that the loop was the conversation's (or the upstream's)
# fault; a second identical failure says the question itself invites it, and more copies
# of the same failure teach nothing.
MAX_CLEAN_RETRIES = 1
CLEAN_RETRY_KINDS = ("degeneration", "budget")

# A validator returns the contract violations it found — empty means the payload holds.
Validator = Callable[[Any], list[str]]


@dataclass(frozen=True)
class LlmUsage:
    """What one task actually spent — reported as a `ComputedMetric` with the evaluation.

    `clean_retries` is how many fresh conversations the answer cost: verdicts that arrive
    after a retry are a shifted population, and calibration must be able to tell
    (ADR-0037 §7)."""

    model: str
    calls: int
    tokens_in: int
    tokens_out: int
    latency_ms: int
    clean_retries: int = 0


@dataclass
class _Spend:
    """Accumulated across every conversation of one task, including the failed rounds."""

    model: str
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0


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
    reasoning: Mapping[str, Any],
) -> tuple[Any, LlmUsage]:
    """One validated JSON payload, or `AssessorExecutionError` — never a half answer."""
    spend = _Spend(model=model)
    for clean_retries in range(MAX_CLEAN_RETRIES + 1):
        try:
            payload = _one_conversation(
                client,
                task_id=task_id,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                validate=validate,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning=reasoning,
                spend=spend,
            )
        except AssessorExecutionError as exc:
            if exc.kind not in CLEAN_RETRY_KINDS or clean_retries == MAX_CLEAN_RETRIES:
                raise
            continue
        return payload, LlmUsage(
            model=spend.model,
            calls=spend.calls,
            tokens_in=spend.tokens_in,
            tokens_out=spend.tokens_out,
            latency_ms=spend.latency_ms,
            clean_retries=clean_retries,
        )
    raise AssertionError("unreachable: the loop returns or raises")


def _one_conversation(
    client: ChatCompletionsClient,
    *,
    task_id: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    validate: Validator,
    temperature: float,
    max_tokens: int,
    reasoning: Mapping[str, Any],
    spend: _Spend,
) -> Any:
    """One conversation from scratch: first ask + feedback rounds, nothing inherited."""
    messages: list[Mapping[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    violations: list[str] = []
    answered: set[str] = set()
    for _ in range(MAX_SCHEMA_ATTEMPTS):
        try:
            completion = client.complete(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                # Whether the judge thinks before answering is part of what it is asked,
                # so it is pinned here and declared in SOURCE_CONFIG, never in the
                # transport (ADR-0034 §1).
                extra_body={"reasoning": dict(reasoning)},
                # Names this question in the trace and nothing else — it never reaches the
                # wire, so it is not part of what the judge is asked (ADR-0034 §5).
                task_id=task_id,
            )
        except LlmConfigurationError as exc:
            raise AssessorExecutionError(
                f"task '{task_id}': {exc}", kind="configuration", task=task_id
            ) from exc
        except LlmTransportError as exc:
            raise AssessorExecutionError(
                f"task '{task_id}': {exc}", kind="transport", task=task_id
            ) from exc
        except LlmError as exc:
            raise AssessorExecutionError(
                f"task '{task_id}': {exc}", kind="response", task=task_id
            ) from exc
        spend.calls += 1
        spend.tokens_in += completion.tokens_in
        spend.tokens_out += completion.tokens_out
        spend.latency_ms += completion.latency_ms
        spend.model = completion.model

        payload, parse_error = _parse_json(completion.text)
        violations = [parse_error] if parse_error else validate(payload)
        if not violations:
            return payload
        # An answer cut off at the token budget is not a mistake feedback can correct: the
        # model ran to the limit, so the same conversation runs to it again. But a FRESH
        # conversation re-rolls the serving (v8): runaways proved stochastic per request —
        # the first field save was cut by one provider and answered cleanly by the same
        # one seconds later — so the outer loop may buy exactly one.
        if completion.finish_reason == "length":
            raise AssessorExecutionError(
                f"task '{task_id}': the model ran to its {max_tokens}-token budget without "
                f"finishing the answer, so what came back cannot be read "
                f"({completion.tokens_out} tokens emitted). Retrying spends the budget on "
                f"the same reply — raise the task's budget or narrow what it asks for. "
                f"First violation: {violations[0]}",
                kind="budget",
                task=task_id,
            )
        # A model that answers the same thing again has not understood the feedback and
        # will not on the next round either: at temperature 0 the same conversation gives
        # the same answer, so the remaining budget would buy a fixed reply. This is the
        # one failure a fresh conversation may dissolve (ADR-0037 §7).
        if completion.text.strip() in answered:
            raise AssessorExecutionError(
                f"task '{task_id}': the model repeated its previous answer verbatim after "
                f"being told what was wrong with it, so the remaining attempts would ask "
                f"the same question and get the same reply. Violations: "
                f"{'; '.join(violations)}",
                kind="degeneration",
                task=task_id,
            )
        answered.add(completion.text.strip())
        messages = [
            *messages,
            {"role": "assistant", "content": completion.text},
            {"role": "user", "content": _feedback(violations)},
        ]
    raise AssessorExecutionError(
        f"task '{task_id}': the model never satisfied the output contract in "
        f"{MAX_SCHEMA_ATTEMPTS} attempts (last violations: {'; '.join(violations)})",
        kind="contract",
        task=task_id,
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
