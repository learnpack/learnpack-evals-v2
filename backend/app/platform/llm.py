"""OpenAI-compatible chat-completions transport (ADR-0034).

Transport, never semantics. This client knows how to reach an endpoint that speaks the
OpenAI chat-completions wire format (OpenRouter today, anything compatible tomorrow) and
how to survive its transient failures: backoff on 429/5xx/timeouts, honoring `Retry-After`.
It does not know models, prompts, schemas or what an answer means — those are assessor
identity and live pinned inside each LLM-carrying assessor package. Changing this file
re-versions no assessor, for the same reason upgrading `httpx` never did: a transport
change may alter whether and when an answer arrives, never which answer arrives.

Environment supplies access, not identity: the API key and the base URL come from
`Settings` at wiring time; the model id always arrives per call, from the assessor's code.
"""

import logging
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

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
    ) -> LlmCompletion:
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

        started = time.monotonic()
        last_transient = ""
        for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
            try:
                response = self._http.post(
                    "/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            except httpx.HTTPError as exc:
                last_transient = f"{type(exc).__name__}: {exc}"
                self._backoff(attempt, retry_after=None, cause=last_transient)
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_transient = f"HTTP {response.status_code}"
                self._backoff(
                    attempt, retry_after=response.headers.get("Retry-After"), cause=last_transient
                )
                continue
            if response.status_code >= 400:
                # A hard 4xx is not transient: retrying an unknown model or a bad request
                # would spend the budget re-asking a question with a fixed answer.
                raise LlmResponseError(
                    f"HTTP {response.status_code} from {response.url}: {response.text[:500]}"
                )
            latency_ms = int((time.monotonic() - started) * 1000)
            return self._parse(response, requested_model=model, latency_ms=latency_ms)

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

    @staticmethod
    def _parse(response: httpx.Response, requested_model: str, latency_ms: int) -> LlmCompletion:
        try:
            body = response.json()
        except ValueError as exc:
            raise LlmResponseError(f"2xx response is not JSON: {response.text[:200]}") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmResponseError(
                f"response carries no message content: {str(body)[:500]}"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LlmResponseError("response content is empty or not text")
        usage = body.get("usage") or {}
        model = body.get("model")
        return LlmCompletion(
            text=content,
            model=model if isinstance(model, str) else requested_model,
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
            latency_ms=latency_ms,
        )
