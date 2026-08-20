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
