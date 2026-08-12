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


def test_what_the_caller_pins_travels_and_cannot_overwrite_the_call():
    """The assessor pins semantic wire fields (`reasoning`); the transport forwards them
    without reading them, and without letting one smuggle in another model."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ok_body())

    client, _ = client_with(handler)
    client.complete(
        model="provider/model",
        messages=MESSAGES,
        extra_body={"reasoning": {"effort": "none"}, "model": "someone/else"},
    )

    payload = json.loads(seen[0].content)
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["model"] == "provider/model"


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


def upstream_error_body(code: int = 502, provider: str = "Sail Research") -> dict:
    """A real OpenRouter 200 whose provider failed — copied from a calibration trace.

    The gateway's own hop succeeded, so the status line says nothing is wrong; the verdict
    is on the choice, next to a message with no content at all."""
    return {
        "provider": provider,
        "model": "vendor/model",
        "choices": [
            {
                "finish_reason": "error",
                "native_finish_reason": None,
                "error": {
                    "code": code,
                    "message": (
                        f"Upstream error from {provider}: response_format violated: "
                        "model emitted invalid JSON: expected value at line 1 column 1"
                    ),
                    "metadata": {"error_type": "provider_unavailable"},
                },
                "message": {"role": "assistant", "content": None, "reasoning": "…"},
            }
        ],
        "usage": {"prompt_tokens": 654, "completion_tokens": 2325},
    }


def test_a_provider_failure_inside_a_200_is_transient():
    """It is a 502 wearing a 200: retrying is exactly the right move, and the gateway
    tends to route the second attempt somewhere else."""
    responses = iter(
        [
            httpx.Response(200, json=upstream_error_body()),
            httpx.Response(200, json=ok_body()),
        ]
    )
    client, sleeps = client_with(lambda request: next(responses))

    assert client.complete(model="m", messages=MESSAGES).text == "answer"
    assert len(sleeps) == 1


def test_a_provider_failure_with_no_retryable_code_is_not_retried():
    """Without a code that says otherwise, re-asking a fixed question only spends the
    budget — the same reason a hard 4xx is not retried."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=upstream_error_body(code=400))

    client, sleeps = client_with(handler)
    with pytest.raises(LlmResponseError, match="upstream error 400"):
        client.complete(model="m", messages=MESSAGES)
    assert len(seen) == 1 and not sleeps


def test_a_provider_failure_is_recorded_with_who_failed():
    client, _ = client_with(lambda request: httpx.Response(200, json=upstream_error_body()))

    calls, sink = observability.recording()
    with observability.collecting(sink):
        with pytest.raises(LlmTransportError):
            client.complete(model="m", messages=MESSAGES)

    # Every attempt names the upstream and its verdict — the two fields that say why.
    assert len(calls) == MAX_TRANSPORT_ATTEMPTS
    assert calls[0].provider == "Sail Research"
    assert calls[0].finish_reason == "error"
    assert "response_format violated" in (calls[0].error or "")


def test_an_answer_the_reasoning_ate_says_so():
    """The real shape of every failed calibration run: a reasoning model bills its
    thinking as output tokens, spends the whole budget on it, and stops having written
    nothing. "content is empty" describes that identically to a dozen other faults."""
    body = {
        "provider": "GMICloud",
        "choices": [
            {
                "finish_reason": "length",
                "message": {"role": "assistant", "content": None, "reasoning": "…" * 3000},
            }
        ],
        "usage": {
            "prompt_tokens": 654,
            "completion_tokens": 2048,
            "completion_tokens_details": {"reasoning_tokens": 2048},
        },
    }
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    client, sleeps = client_with(handler)
    with pytest.raises(LlmResponseError) as raised:
        client.complete(model="m", messages=MESSAGES)

    message = str(raised.value)
    assert "2048 completion tokens of which 2048 were reasoning" in message
    assert "max_tokens" in message and "reasoning off" in message
    # Not retried: the limit produces the same answer every time, and retrying would
    # hide a misconfiguration behind a delay.
    assert len(seen) == 1 and not sleeps


def test_an_empty_answer_with_no_limit_to_blame_stays_generic():
    client, _ = client_with(lambda request: httpx.Response(200, json=ok_body(content="   ")))
    with pytest.raises(LlmResponseError, match="empty or not text"):
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


def test_a_record_carries_how_the_model_was_sampled():
    """The other half of the question. A wrong answer is traced to it as often as to the
    prompt — v1 of `drafts-hybrid` failed every run on sampling, with prompts intact."""
    client, _ = client_with(lambda request: httpx.Response(200, json=ok_body()))

    calls, sink = observability.recording()
    with observability.collecting(sink):
        client.complete(
            model="provider/model",
            messages=MESSAGES,
            max_tokens=8000,
            response_format={"type": "json_object"},
            extra_body={"reasoning": {"effort": "none"}},
        )

    (call,) = calls
    assert call.sampling == {
        "temperature": 0.0,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
        "reasoning": {"effort": "none"},
    }
    # The conversation and the model are fields of their own; this is what is left.
    assert "messages" not in call.sampling and "model" not in call.sampling


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
