"""OpenAI-compatible chat-completions transport (ADR-0034).

Transport, never semantics. This client knows how to reach an endpoint that speaks the
OpenAI chat-completions wire format (OpenRouter today, anything compatible tomorrow) and
how to survive its transient failures: backoff on 429/5xx/timeouts, honoring `Retry-After`,
and on the upstream failures such a gateway delivers *inside* a 200 — its own hop
succeeded, the provider behind it did not.
It does not know models, prompts, schemas or what an answer means — those are assessor
identity and live pinned inside each LLM-carrying assessor package. Changing this file
re-versions no assessor, for the same reason upgrading `httpx` never did: a transport
change may alter whether and when an answer arrives, never which answer arrives.

Environment supplies access, not identity: the API key and the base URL come from
`Settings` at wiring time; the model id always arrives per call, from the assessor's code.

Every attempt is announced to `app.platform.observability` — what was sent, what came
back, what it cost — so a caller that wants a trace gets one without this module knowing
who is listening. Announcing an answer does not change which answer arrives, so it
re-versions no assessor either (ADR-0034 §1).
"""

import logging
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.platform import observability

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60.0
# 4 attempts ~ three backoffs; enough for a rate-limit burst, short enough that a dead
# endpoint fails in well under two minutes.
MAX_TRANSPORT_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_CAP_SECONDS = 20.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class LlmError(Exception):
    """Base of everything this transport can raise."""


class LlmConfigurationError(LlmError):
    """The environment supplies no access (missing API key) — a wiring problem."""


class LlmTransportError(LlmError):
    """Transient transport failures exhausted the retry budget."""


class LlmResponseError(LlmError):
    """The endpoint answered, but with something no caller can use (or a hard 4xx)."""


@dataclass(frozen=True)
class LlmCompletion:
    """One usable answer, with the observability the caller reports as metrics."""

    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    # Recorded, not acted upon: a `length` here means the answer was cut off, which the
    # caller currently meets as "the answer is not valid JSON". Naming it in the trace is
    # what lets that diagnosis be made at all.
    finish_reason: str | None = None
    provider: str | None = None


class ChatCompletionsClient:
    """POST `{base_url}/chat/completions`, retrying what is transient, typing what is not.

    `transport` and `sleep` exist for tests (httpx.MockTransport, no real waiting); the
    defaults are the real network and the real clock.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    def complete(
        self,
        *,
        model: str,
        messages: Sequence[Mapping[str, str]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        task_id: str | None = None,
    ) -> LlmCompletion:
        """`task_id` names the caller's question in the trace; it never reaches the wire.

        `extra_body` is wire fields the CALLER pins — `reasoning`, `provider` routing,
        whatever the endpoint understands. They are forwarded verbatim and never read
        here: what they mean is the assessor's identity, and a transport that interpreted
        them would be deciding something (ADR-0034 §1). They cannot overwrite the fields
        this method owns, so nothing can smuggle in another `model`.
        """
        if not self._api_key:
            raise LlmConfigurationError(
                "no LLM API key configured — set LLM_API_KEY (the key is environment, "
                "never part of an assessor's identity, ADR-0034)"
            )
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format is not None:
            payload["response_format"] = dict(response_format)
        for field, value in (extra_body or {}).items():
            payload.setdefault(field, value)

        sent = observability.messages_of(messages)
        started = time.monotonic()
        last_transient = ""
        for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
            attempt_started = time.monotonic()
            try:
                response = self._http.post(
                    "/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            except httpx.HTTPError as exc:
                last_transient = f"{type(exc).__name__}: {exc}"
                _observe(task_id, attempt, model, sent, attempt_started, error=last_transient)
                self._backoff(attempt, retry_after=None, cause=last_transient)
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_transient = f"HTTP {response.status_code}"
                _observe(
                    task_id,
                    attempt,
                    model,
                    sent,
                    attempt_started,
                    response_text=response.text,
                    error=last_transient,
                )
                self._backoff(
                    attempt, retry_after=response.headers.get("Retry-After"), cause=last_transient
                )
                continue
            if response.status_code >= 400:
                # A hard 4xx is not transient: retrying an unknown model or a bad request
                # would spend the budget re-asking a question with a fixed answer.
                detail = f"HTTP {response.status_code} from {response.url}: {response.text[:500]}"
                _observe(
                    task_id,
                    attempt,
                    model,
                    sent,
                    attempt_started,
                    response_text=response.text,
                    error=detail,
                )
                raise LlmResponseError(detail)
            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                body = _body(response)
            except LlmResponseError as exc:
                # A 2xx nobody can use is still an answer the trace must carry: it is the
                # only place the unusable body can be read afterwards.
                _observe(
                    task_id,
                    attempt,
                    model,
                    sent,
                    attempt_started,
                    response_text=response.text,
                    error=str(exc),
                )
                raise

            upstream = _upstream_error(body)
            if upstream is not None:
                code, message = upstream
                detail = f"upstream error {code}: {message}"
                _observe(
                    task_id,
                    attempt,
                    model,
                    sent,
                    attempt_started,
                    response_text=response.text,
                    error=detail,
                    provider=_provider(body),
                    finish_reason=_finish_reason(body),
                )
                if code in RETRYABLE_STATUS:
                    last_transient = detail
                    self._backoff(attempt, retry_after=None, cause=last_transient)
                    continue
                raise LlmResponseError(detail)

            try:
                completion = _completion(body, requested_model=model, latency_ms=latency_ms)
            except LlmResponseError as exc:
                _observe(
                    task_id,
                    attempt,
                    model,
                    sent,
                    attempt_started,
                    response_text=response.text,
                    error=str(exc),
                    provider=_provider(body),
                    finish_reason=_finish_reason(body),
                )
                raise
            _observe(task_id, attempt, model, sent, attempt_started, completion=completion)
            return completion

        raise LlmTransportError(
            f"transport retry budget exhausted after {MAX_TRANSPORT_ATTEMPTS} attempts "
            f"(last failure: {last_transient})"
        )

    def _backoff(self, attempt: int, retry_after: str | None, cause: str) -> None:
        if attempt >= MAX_TRANSPORT_ATTEMPTS:
            return  # the loop falls through to LlmTransportError; no pointless final sleep
        delay = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        delay *= 0.5 + random.random() / 2  # jitter, so parallel callers do not stampede
        if retry_after is not None:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass  # an HTTP-date Retry-After: the backoff schedule is a fine substitute
        logger.warning(
            "LLM transport attempt %d failed (%s); retrying in %.1fs", attempt, cause, delay
        )
        self._sleep(delay)


def _body(response: httpx.Response) -> Any:
    """The decoded 2xx body, or the error for a caller that got prose instead of JSON."""
    try:
        return response.json()
    except ValueError as exc:
        raise LlmResponseError(f"2xx response is not JSON: {response.text[:200]}") from exc


def _choice(body: Any) -> Mapping[str, Any]:
    """The first choice, or an empty mapping — every reader here tolerates its absence."""
    if isinstance(body, dict):
        choices = body.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            return choices[0]
    return {}


def _provider(body: Any) -> str | None:
    """Which upstream actually served the request, when the gateway says so."""
    provider = body.get("provider") if isinstance(body, dict) else None
    return provider if isinstance(provider, str) else None


def _finish_reason(body: Any) -> str | None:
    reason = _choice(body).get("finish_reason")
    return reason if isinstance(reason, str) else None


def _upstream_error(body: Any) -> tuple[int, str] | None:
    """The provider's own failure, delivered inside a 200.

    A gateway that routes to several upstreams answers 200 for its own hop and carries the
    upstream's verdict in the payload — `{"code": 502, "message": "…", "metadata": …}`,
    either at the top level or on the choice. Read as a successful answer it looks like a
    reply with nothing in it, which is the least informative thing it could be mistaken for.
    """
    if not isinstance(body, dict):
        return None
    for candidate in (body.get("error"), _choice(body).get("error")):
        if not isinstance(candidate, dict):
            continue
        raw_code = candidate.get("code")
        code = raw_code if isinstance(raw_code, int) and not isinstance(raw_code, bool) else 0
        return code, str(candidate.get("message") or candidate)
    return None


def _empty_content_error(body: Any) -> str:
    """Why there is no answer — named, because the cure differs per cause.

    A reasoning model bills its thinking as output tokens, so `max_tokens` is a budget
    the reasoning can spend entirely: it stops at the limit having written nothing. The
    generic wording ("content is empty") describes that identically to a dozen unrelated
    faults, and it is what made four calibration runs unreadable. Retrying is not the
    remedy here and the message says so — the limit produces the same answer every time.
    """
    usage = (body.get("usage") if isinstance(body, dict) else None) or {}
    spent = int(usage.get("completion_tokens") or 0)
    reasoning = int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
    if _finish_reason(body) == "length":
        return (
            f"the model stopped at the token limit without emitting an answer "
            f"(finish_reason=length, {spent} completion tokens of which {reasoning} were "
            f"reasoning): the budget was spent before the answer began. Retrying will not "
            f"help — raise the task's max_tokens, or turn the model's reasoning off."
        )
    return "response content is empty or not text"


def _completion(body: Any, requested_model: str, latency_ms: int) -> LlmCompletion:
    choice = _choice(body)
    try:
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmResponseError(f"response carries no message content: {str(body)[:500]}") from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmResponseError(_empty_content_error(body))
    usage = body.get("usage") or {}
    model = body.get("model")
    return LlmCompletion(
        text=content,
        model=model if isinstance(model, str) else requested_model,
        tokens_in=int(usage.get("prompt_tokens") or 0),
        tokens_out=int(usage.get("completion_tokens") or 0),
        latency_ms=latency_ms,
        finish_reason=_finish_reason(body),
        provider=_provider(body),
    )


def _observe(
    task_id: str | None,
    attempt: int,
    model: str,
    messages: tuple[Mapping[str, str], ...],
    started: float,
    *,
    completion: LlmCompletion | None = None,
    response_text: str | None = None,
    error: str | None = None,
    provider: str | None = None,
    finish_reason: str | None = None,
) -> None:
    """Announce one attempt — successful or not — to whoever is listening.

    A failed attempt passes `provider` and `finish_reason` explicitly: they are the two
    fields that say WHY it failed, and they are readable long before the answer is usable.
    """
    observability.emit(
        observability.LlmCall(
            task_id=task_id,
            attempt=attempt,
            model_requested=model,
            messages=messages,
            latency_ms=int((time.monotonic() - started) * 1000),
            model_answered=completion.model if completion is not None else None,
            provider=completion.provider if completion is not None else provider,
            response_text=completion.text if completion is not None else response_text,
            finish_reason=completion.finish_reason if completion is not None else finish_reason,
            tokens_in=completion.tokens_in if completion is not None else 0,
            tokens_out=completion.tokens_out if completion is not None else 0,
            error=error,
        )
    )
