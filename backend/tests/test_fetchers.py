"""The shared transport: what it fetches, how many times it dials, and how much it asks for
at once."""

import threading
from pathlib import Path

import httpx
import pytest

from app.platform.concurrency import all_at_once
from app.shared.infrastructure import fetchers
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher, HttpFetcher


@pytest.fixture
def served() -> httpx.MockTransport:
    """Anything under /ok answers; anything else is a 404."""

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/ok"):
            return httpx.Response(200, content=b"artifact bytes")
        return httpx.Response(404)

    return httpx.MockTransport(handle)


def test_it_fetches_and_translates_a_miss(served):
    fetcher = HttpFetcher(transport=served)
    assert fetcher.fetch("http://example.test/ok/lesson.md") == b"artifact bytes"
    with pytest.raises(FetchError) as refused:
        fetcher.fetch("http://example.test/missing.md")
    # Neutral on purpose: what a miss MEANS is each module's boundary to decide.
    assert "could not fetch artifact" in str(refused.value)


def test_many_artifacts_do_not_open_many_clients(monkeypatch, served):
    """The regression this file exists for.

    A package is fetched an artifact at a time — dozens per course — and `httpx.get` dials
    and re-resolves on every call. On a host where the name resolves to something that does
    not answer, that cost two seconds per artifact and made reading one course take three
    minutes. Counting clients rather than timing anything: a timing test would be flaky and
    would not say what broke.
    """
    monkeypatch.setattr(fetchers, "_shared_client", None)
    built = 0
    real = httpx.Client

    def counted(*args, **kwargs):
        nonlocal built
        built += 1
        kwargs.setdefault("transport", served)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", counted)

    fetcher = HttpFetcher()
    for index in range(25):
        assert fetcher.fetch(f"http://example.test/ok/{index}.md") == b"artifact bytes"

    assert built == 1


def test_a_second_fetcher_shares_the_same_client(monkeypatch, served):
    """Callers build one fetcher per use case and none of them closes it, so the client has
    to outlive them — otherwise every profiling call would leave sockets behind."""
    monkeypatch.setattr(fetchers, "_shared_client", None)
    built = 0
    real = httpx.Client

    def counted(*args, **kwargs):
        nonlocal built
        built += 1
        kwargs.setdefault("transport", served)
        return real(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", counted)

    HttpFetcher().fetch("http://example.test/ok/a.md")
    HttpFetcher(timeout_seconds=30.0).fetch("http://example.test/ok/b.md")

    assert built == 1


def test_an_injected_transport_gets_a_client_and_a_gate_of_its_own(monkeypatch, served):
    """A test must not inherit connections or slots from another, nor leave any in the
    shared ones."""
    monkeypatch.setattr(fetchers, "_shared_client", None)
    monkeypatch.setattr(fetchers, "_shared_slots", None)

    HttpFetcher(transport=served).fetch("http://example.test/ok/a.md")

    assert fetchers._shared_client is None
    assert fetchers._shared_slots is None


def test_the_gate_bounds_what_the_origin_is_asked_for_at_once():
    """The ceiling, pinned with a barrier rather than a stopwatch (as `test_concurrency.py`
    pins the other half): the ceiling's worth of fetches have to be able to meet inside the
    origin, and no more than that many are ever there. A serial fetcher never trips the
    barrier and an ungated one drives the peak past it, so both failures are real failures
    rather than a timing threshold to tune."""
    ceiling = 3
    in_flight = 0
    peak = 0
    counted = threading.Lock()
    met = threading.Barrier(ceiling, timeout=20)

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, peak
        with counted:
            in_flight += 1
            peak = max(peak, in_flight)
        met.wait()  # nobody is answered until a full ceiling's worth has arrived
        with counted:
            in_flight -= 1
        return httpx.Response(200, content=b"artifact bytes")

    fetcher = HttpFetcher(transport=httpx.MockTransport(handle), max_concurrency=ceiling)
    locators = [f"http://example.test/ok/{index}.md" for index in range(12)]

    assert list(all_at_once(fetcher.fetch, locators)) == [b"artifact bytes"] * 12
    assert peak == ceiling


def test_a_fetcher_that_asked_for_a_gate_does_not_share_the_processs_one():
    """Two fetchers that each allow one request at a time still run at the same time. The
    gate belongs to whoever asked for it, exactly like the client — a global gate of one
    would leave this barrier waiting forever."""
    met = threading.Barrier(2, timeout=20)

    def handle(request: httpx.Request) -> httpx.Response:
        met.wait()
        return httpx.Response(200, content=b"artifact bytes")

    fetchers_with_one_slot = [
        HttpFetcher(transport=httpx.MockTransport(handle), max_concurrency=1) for _ in range(2)
    ]
    fetched = all_at_once(
        lambda fetcher: fetcher.fetch("http://example.test/ok/a.md"), fetchers_with_one_slot
    )

    assert list(fetched) == [b"artifact bytes"] * 2


def test_the_filesystem_fetcher_refuses_to_escape_its_base(tmp_path: Path):
    (tmp_path / "inside.md").write_bytes(b"here")
    (tmp_path.parent / "outside.md").write_bytes(b"elsewhere")
    fetcher = FilesystemFetcher(tmp_path)

    assert fetcher.fetch("inside.md") == b"here"
    with pytest.raises(FetchError):
        fetcher.fetch("../outside.md")


# --------------------------------------------------- an origin's bad moments (retries)
# Everything here runs against `httpx.MockTransport` with an injected sleep — no network,
# no real waiting — which is the shape `tests/test_llm_client.py` uses for the same policy
# at the other transport.


def fetcher_with(handler, **kwargs):
    sleeps: list[float] = []
    return (
        HttpFetcher(transport=httpx.MockTransport(handler), sleep=sleeps.append, **kwargs),
        sleeps,
    )


def answering(*responses):
    """One handler that answers each call with the next response in turn."""
    remaining = iter(responses)

    def handle(request: httpx.Request) -> httpx.Response:
        answer = next(remaining)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return handle


def test_a_server_error_is_the_origins_weather_not_its_answer():
    fetcher, sleeps = fetcher_with(
        answering(httpx.Response(503), httpx.Response(200, content=b"artifact bytes"))
    )

    assert fetcher.fetch("http://example.test/ok/lesson.md") == b"artifact bytes"
    assert len(sleeps) == 1


def test_a_dropped_connection_is_transient_too():
    fetcher, sleeps = fetcher_with(
        answering(httpx.ConnectError("connection reset"), httpx.Response(200, content=b"bytes"))
    )

    assert fetcher.fetch("http://example.test/ok/lesson.md") == b"bytes"
    assert len(sleeps) == 1


def test_a_miss_is_answered_at_once_and_never_waited_on():
    """The one that matters most on this transport. A 404 is not a failure to reach the
    origin, it is the package saying it carries no such artifact — a syllabus, most often,
    whose absence is a recorded state read on EVERY registration (ADR-0022). Retrying it
    would tax every package that is fine."""
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(404)

    fetcher, sleeps = fetcher_with(handle)

    with pytest.raises(FetchError):
        fetcher.fetch("http://example.test/.learn/initialSyllabus.json")

    assert len(seen) == 1 and not sleeps


def test_an_origin_that_stays_down_exhausts_the_budget_and_names_the_locator():
    fetcher, sleeps = fetcher_with(lambda request: httpx.Response(503))

    with pytest.raises(FetchError) as refused:
        fetcher.fetch("http://example.test/ok/lesson.md")

    assert "could not fetch artifact 'http://example.test/ok/lesson.md'" in str(refused.value)
    # No sleep after the final attempt: the caller gets the error, not a pointless wait.
    assert len(sleeps) == fetchers.MAX_FETCH_ATTEMPTS - 1


def test_a_rate_limited_origin_is_waited_on_as_long_as_it_asked():
    fetcher, sleeps = fetcher_with(
        answering(
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, content=b"bytes"),
        )
    )

    assert fetcher.fetch("http://example.test/ok/lesson.md") == b"bytes"
    assert len(sleeps) == 1 and sleeps[0] >= 3.0


def test_the_gate_is_not_held_while_waiting():
    """A slot held through a backoff would be an idle slot: the gate bounds what the ORIGIN
    is asked to do at once, and a caller that is sleeping is asking for nothing.

    Pinned by making the wait itself the observation. With room for exactly one request, the
    backoff starts a second fetch and waits for it: it can only finish if the first one gave
    its slot back, so a slot held through a backoff deadlocks here instead of passing slowly.
    """
    attempts = 0
    served: list[bytes] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        if request.url.path.endswith("first.md"):
            attempts += 1
            if attempts == 1:
                return httpx.Response(503)  # into a backoff, which should free the slot
        return httpx.Response(200, content=b"bytes")

    def waiting(delay: float) -> None:
        other = threading.Thread(
            target=lambda: served.append(fetcher.fetch("http://example.test/ok/other.md"))
        )
        other.start()
        other.join(timeout=20)
        assert served, "the slot was still held while the fetch waited to retry"

    fetcher = HttpFetcher(transport=httpx.MockTransport(handle), sleep=waiting, max_concurrency=1)

    assert fetcher.fetch("http://example.test/ok/first.md") == b"bytes"
    assert served == [b"bytes"]
