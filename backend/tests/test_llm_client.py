"""The platform LLM transport (ADR-0034): retries what is transient, types what is not.

Everything runs against `httpx.MockTransport` with an injected sleep — no network, no
real waiting. What is pinned here is the transport CONTRACT the assessors rely on:
transient failures are absorbed up to a budget, hard failures surface immediately, and a
2xx that cannot be used is an error, never a half answer.

The second half pins the OTHER contract this transport owes: one trace record per
attempt, carrying what was sent and what came back, and never — under any failure of the
listener — changing the answer the caller receives.
"""

import json

import httpx
import pytest

from app.platform import observability
from app.platform.llm import (
    MAX_TRANSPORT_ATTEMPTS,
    ChatCompletionsClient,
    LlmConfigurationError,
    LlmResponseError,
    LlmTransportError,
)

MESSAGES = [{"role": "user", "content": "hello"}]


def ok_body(content: str = "answer", finish_reason: str = "stop") -> dict:
    return {
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        "model": "provider/model-echoed",
        "provider": "TheOneThatAnswered",
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


# ------------------------------------------------------------------ what the trace sees
#
# One record per ATTEMPT, successful or not: a run that failed has nothing else to show
# for itself, and the retries are the part worth reading.


def test_nothing_is_recorded_when_nobody_is_listening():
    client, _ = client_with(lambda request: httpx.Response(200, json=ok_body()))
    client.complete(model="m", messages=MESSAGES)  # outside any collector

    calls, sink = observability.recording()
    with observability.collecting(sink):
        client.complete(model="m", messages=MESSAGES)

    assert len(calls) == 1  # only the call made while someone was listening


def test_a_record_carries_what_was_sent_and_what_came_back():
    client, _ = client_with(lambda request: httpx.Response(200, json=ok_body()))

    calls, sink = observability.recording()
    with observability.collecting(sink):
        client.complete(model="provider/model", messages=MESSAGES, task_id="outcomes")

    (call,) = calls
    assert call.task_id == "outcomes" and call.attempt == 1 and call.ok
    assert call.messages == ({"role": "user", "content": "hello"},)
    assert call.model_requested == "provider/model"
    assert call.model_answered == "provider/model-echoed"
    assert call.provider == "TheOneThatAnswered"
    assert call.response_text == "answer"
    assert call.finish_reason == "stop"
    assert (call.tokens_in, call.tokens_out) == (10, 5)


def test_a_truncated_answer_is_recorded_as_such():
    """`length` is recorded, not acted upon — naming it is what allows the diagnosis."""
    body = ok_body(content='{"outcomes": [', finish_reason="length")
    client, _ = client_with(lambda request: httpx.Response(200, json=body))

    calls, sink = observability.recording()
    with observability.collecting(sink):
        completion = client.complete(model="m", messages=MESSAGES)

    assert completion.finish_reason == "length"  # the caller still gets its answer
    assert calls[0].finish_reason == "length"


def test_every_attempt_is_recorded_including_the_transient_ones():
    responses = iter([httpx.Response(429, text="slow down"), httpx.Response(200, json=ok_body())])
    client, _ = client_with(lambda request: next(responses))

    calls, sink = observability.recording()
    with observability.collecting(sink):
        client.complete(model="m", messages=MESSAGES)

    assert [(c.attempt, c.ok) for c in calls] == [(1, False), (2, True)]
    assert calls[0].error == "HTTP 429" and calls[0].response_text == "slow down"


def test_a_hard_failure_is_recorded_before_it_is_raised():
    client, _ = client_with(lambda request: httpx.Response(404, json={"error": "unknown model"}))

    calls, sink = observability.recording()
    with observability.collecting(sink), pytest.raises(LlmResponseError):
        client.complete(model="m", messages=MESSAGES)

    (call,) = calls
    assert not call.ok and "HTTP 404" in (call.error or "")
    assert "unknown model" in (call.response_text or "")


def test_an_unusable_2xx_leaves_its_raw_body_in_the_record():
    """The only place the unreadable answer can be read afterwards."""
    client, _ = client_with(lambda request: httpx.Response(200, text="Sure! Here is the JSON:"))

    calls, sink = observability.recording()
    with observability.collecting(sink), pytest.raises(LlmResponseError):
        client.complete(model="m", messages=MESSAGES)

    assert calls[0].response_text == "Sure! Here is the JSON:"
    assert "not JSON" in (calls[0].error or "")


def test_a_broken_sink_does_not_break_the_call():
    """Observing never changes the observed."""

    def explode(call: observability.LlmCall) -> None:
        raise RuntimeError("the listener is broken")

    client, _ = client_with(lambda request: httpx.Response(200, json=ok_body()))
    with observability.collecting(explode):
        assert client.complete(model="m", messages=MESSAGES).text == "answer"


def test_the_recorded_conversation_is_a_snapshot():
    """The caller keeps appending to its own list between attempts (the feedback loop)."""
    messages = [{"role": "user", "content": "first"}]
    client, _ = client_with(lambda request: httpx.Response(200, json=ok_body()))

    calls, sink = observability.recording()
    with observability.collecting(sink):
        client.complete(model="m", messages=messages)
        messages.append({"role": "user", "content": "second"})
        client.complete(model="m", messages=messages)

    assert len(calls[0].messages) == 1 and len(calls[1].messages) == 2
