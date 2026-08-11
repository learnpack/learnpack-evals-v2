"""The platform LLM transport (ADR-0034): retries what is transient, types what is not.

Everything runs against `httpx.MockTransport` with an injected sleep — no network, no
real waiting. What is pinned here is the transport CONTRACT the assessors rely on:
transient failures are absorbed up to a budget, hard failures surface immediately, and a
2xx that cannot be used is an error, never a half answer.
"""

import json

import httpx
import pytest

from app.platform.llm import (
    MAX_TRANSPORT_ATTEMPTS,
    ChatCompletionsClient,
    LlmConfigurationError,
    LlmResponseError,
    LlmTransportError,
)

MESSAGES = [{"role": "user", "content": "hello"}]


def ok_body(content: str = "answer") -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": "provider/model-echoed",
    }


def client_with(handler, api_key: str = "key") -> tuple[ChatCompletionsClient, list[float]]:
    sleeps: list[float] = []
    client = ChatCompletionsClient(
        base_url="https://test.example/v1",
        api_key=api_key,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )
    return client, sleeps


def test_a_usable_answer_comes_back_with_its_usage():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ok_body())

    client, sleeps = client_with(handler)
    completion = client.complete(model="provider/model", messages=MESSAGES)

    assert completion.text == "answer"
    assert completion.model == "provider/model-echoed"  # the endpoint's word, when given
    assert (completion.tokens_in, completion.tokens_out) == (10, 5)
    assert not sleeps

    request = seen[0]
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer key"
    payload = json.loads(request.content)
    assert payload["model"] == "provider/model"
    assert payload["temperature"] == 0.0


def test_a_rate_limit_is_retried_honoring_retry_after():
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, json=ok_body()),
        ]
    )
    client, sleeps = client_with(lambda request: next(responses))

    completion = client.complete(model="m", messages=MESSAGES)

    assert completion.text == "answer"
    assert len(sleeps) == 1 and sleeps[0] >= 3.0


def test_persistent_server_errors_exhaust_the_budget():
    client, sleeps = client_with(lambda request: httpx.Response(503))

    with pytest.raises(LlmTransportError, match="HTTP 503"):
        client.complete(model="m", messages=MESSAGES)
    # No sleep after the final attempt: the caller gets the error, not a pointless wait.
    assert len(sleeps) == MAX_TRANSPORT_ATTEMPTS - 1


def test_a_dropped_connection_is_transient():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection dropped")
        return httpx.Response(200, json=ok_body())

    client, sleeps = client_with(handler)
    assert client.complete(model="m", messages=MESSAGES).text == "answer"
    assert len(sleeps) == 1


def test_a_hard_4xx_is_not_retried():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(404, json={"error": "unknown model"})

    client, sleeps = client_with(handler)
    with pytest.raises(LlmResponseError, match="HTTP 404"):
        client.complete(model="m", messages=MESSAGES)
    assert len(seen) == 1 and not sleeps  # a fixed answer: re-asking cannot change it


def test_an_unusable_2xx_is_an_error_not_a_half_answer():
    client, _ = client_with(lambda request: httpx.Response(200, text="not json"))
    with pytest.raises(LlmResponseError, match="not JSON"):
        client.complete(model="m", messages=MESSAGES)

    client, _ = client_with(lambda request: httpx.Response(200, json={"choices": []}))
    with pytest.raises(LlmResponseError, match="no message content"):
        client.complete(model="m", messages=MESSAGES)

    client, _ = client_with(lambda request: httpx.Response(200, json=ok_body(content="   ")))
    with pytest.raises(LlmResponseError, match="empty"):
        client.complete(model="m", messages=MESSAGES)


def test_a_missing_key_fails_before_touching_the_network():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ok_body())

    client, _ = client_with(handler, api_key="")
    with pytest.raises(LlmConfigurationError, match="LLM_API_KEY"):
        client.complete(model="m", messages=MESSAGES)
    assert not seen
