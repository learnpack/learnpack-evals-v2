"""Cancelling long work — the scope, and the transport that honours it.

Two properties are worth pinning and they are both about *not* happening: a cancelled run
issues no further requests, and nothing on the path can quietly turn the stop into an
error. The second is what keeps a cancelled evaluation from persisting as a run full of
`execution_error` — a record of judgments nobody made.
"""

import threading

import httpx
import pytest

from app.platform import cancellation
from app.platform.cancellation import CancellationToken, Cancelled, cancel_scope
from app.platform.llm import ChatCompletionsClient

MESSAGES = [{"role": "user", "content": "hello"}]


def ok_body() -> dict:
    return {
        "choices": [{"message": {"content": "answer"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }


def client_for(requests: list[httpx.Request]) -> ChatCompletionsClient:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=ok_body())

    return ChatCompletionsClient(
        base_url="https://test.example/v1", api_key="key", transport=httpx.MockTransport(handler)
    )


def test_outside_a_scope_nothing_is_cancellable():
    """Every caller that predates cancellation stays unaware it exists."""
    requests: list[httpx.Request] = []
    assert client_for(requests).complete(model="m", messages=MESSAGES).text == "answer"
    assert len(requests) == 1
    cancellation.check()  # no scope, no token, no effect


def test_a_cancelled_scope_stops_the_next_request_before_it_is_sent():
    """The check sits before the call, not after: the point is the request that never
    costs anything, not a tidier error on one already paid for."""
    requests: list[httpx.Request] = []
    client = client_for(requests)
    token = CancellationToken()

    with cancel_scope(token):
        assert client.complete(model="m", messages=MESSAGES).text == "answer"
        token.cancel()
        with pytest.raises(Cancelled):
            client.complete(model="m", messages=MESSAGES)

    assert len(requests) == 1  # the second never reached the endpoint


def test_cancelled_is_not_an_exception_anyone_can_swallow():
    """`BaseException`, like `KeyboardInterrupt`: the assessors' `except Exception` guards
    exist to turn a broken call into a typed failure, and a stop is not a failure. If one
    of them absorbed this, a cancelled run would persist as an evaluation of errors."""
    assert issubclass(Cancelled, BaseException)
    assert not issubclass(Cancelled, Exception)

    token = CancellationToken()
    token.cancel()
    with cancel_scope(token):
        try:
            cancellation.check()
        except Exception:  # noqa: BLE001 — the point of the test
            pytest.fail("a broad `except Exception` must not catch a cancellation")
        except Cancelled:
            pass


def test_a_token_reaches_the_thread_that_enters_the_scope():
    """A worker installs the scope itself: a new thread starts with an empty context, which
    is what makes "this run's token" mean this run's when several share the process."""
    token = CancellationToken()
    token.cancel()
    seen: list[str] = []

    def worker(install: bool) -> None:
        if install:
            with cancel_scope(token):
                try:
                    cancellation.check()
                except Cancelled:
                    seen.append("stopped")
                return
        cancellation.check()  # no scope in this thread: unaffected
        seen.append("ran")

    for install in (True, False):
        thread = threading.Thread(target=worker, args=(install,))
        thread.start()
        thread.join()

    assert seen == ["stopped", "ran"]


def test_leaving_a_scope_restores_the_previous_one():
    outer, inner = CancellationToken(), CancellationToken()
    inner.cancel()

    with cancel_scope(outer):
        with cancel_scope(inner), pytest.raises(Cancelled):
            cancellation.check()
        cancellation.check()  # back under `outer`, which nobody cancelled
