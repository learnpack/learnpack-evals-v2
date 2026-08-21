"""Locator → bytes fetchers — shared technical transport, no domain knowledge.

One implementation instead of per-module twins. Module isolation is untouched: each module
keeps its own Protocol port (structural typing) and its own failure *meaning* — a fetch
miss is a soft absent brief in the registry's intake, a failed extraction in profiling, a
refused registration in discovery. That translation happens at each module's boundary;
`FetchError` stays deliberately neutral.

It is also where the ceiling on artifact requests lives, for the reason the LLM transport
gives for its own (ADR-0040 §1, ADR-0048 §7): the transport is the only place that sees every
call however many levels of fan-out sit above it, and a cap per level would leave nobody
having decided their product. Callers may therefore ask for a whole package at once without
knowing how many requests that releases.

And it is where an origin's bad moments are survived, on the policy `llm.py` already settled
for the other transport: back off on the failures that are the endpoint's weather rather than
its answer, honour `Retry-After`, jitter so parallel callers do not stampede. The difference
this transport forces is that **a miss is a legitimate answer here** — a package without a
syllabus registers with an absent brief (ADR-0022), and that is read on every registration —
so a 404 is returned at once and never retried.
"""

import logging
import random
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# 3 attempts ~ two backoffs. One below the LLM transport's, because the unit that pays is
# different: there one call is one answer worth waiting for, here one COURSE is dozens of
# fetches, so a budget multiplies by the artifacts of a package and then by the courses of a
# batch. Two backoffs still absorb a burst; what they do not absorb is an origin that is gone,
# and a dead one fails a course on its very first fetch, before any fan-out.
MAX_FETCH_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 1.0
BACKOFF_CAP_SECONDS = 10.0
# The endpoint's weather, not its answer. Every other 4xx is a fact about what was asked for,
# and re-asking cannot change it — least of all a 404, which is how a package says it carries
# no syllabus.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class FetchError(Exception):
    """The locator could not be fetched or read. What that *means* is the caller's
    boundary to decide — this exception carries no module's semantics."""


#: One client for the process, so a connection is dialled once and then kept.
#:
#: `httpx.get` opens a connection and resolves the host again on every call, and a package
#: is fetched an artifact at a time — 73 of them for one course here. That is invisible
#: until the host is one where the name resolves to something that does not answer:
#: `localhost` tries `::1` first on Windows, waits out the failure, and falls back to IPv4,
#: which cost two seconds PER ARTIFACT and turned reading one course into three minutes of
#: waiting for 459 KiB. Reusing the connection made the same course half a second.
#:
#: Shared rather than per instance because the callers build a fetcher per use case and
#: none of them closes it: an instance-owned client would leave its sockets to the garbage
#: collector. `httpx.Client` is thread-safe, which is what makes one for everybody safe.
_shared_client: httpx.Client | None = None
#: The gate, beside the client it gates. One per process, so it is the ceiling on everything:
#: a discovery asking for a package's leaves at once and a profiling run reading another are
#: the same requests to whoever is serving them.
_shared_slots: threading.BoundedSemaphore | None = None
_shared_lock = threading.Lock()


def _client() -> httpx.Client:
    global _shared_client
    with _shared_lock:
        if _shared_client is None:
            _shared_client = httpx.Client(follow_redirects=True)
        return _shared_client


def _slots() -> threading.BoundedSemaphore:
    global _shared_slots
    with _shared_lock:
        if _shared_slots is None:
            _shared_slots = threading.BoundedSemaphore(_ceiling())
        return _shared_slots


def _ceiling(max_concurrency: int | None = None) -> int:
    declared = get_settings().http_max_concurrency if max_concurrency is None else max_concurrency
    return max(1, declared)


class HttpFetcher:
    """Artifacts over http, on a connection that outlives the fetch, behind a gate.

    The timeout stays per instance and travels with each request — it was the only thing
    that told one fetcher from another, and it does not justify a client of its own.

    The gate is the opposite: it belongs to the process, not to the fetcher, because callers
    build one of these per use case and what has to be bounded is what the ORIGIN is being
    asked to do. It is set lower than the LLM transport's for a reason that is not about
    capacity (`config.py`): the account is not ours, and a fetch that runs out of attempts
    refuses a whole registration.
    """

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        max_concurrency: int | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._timeout = timeout_seconds
        self._sleep = sleep
        # Either argument makes this fetcher private — its own client AND its own gate. A test
        # must not inherit connections or slots from another, nor leave any behind in the
        # shared ones, and a ceiling that silently applied to everybody would be worse than
        # no argument at all.
        private = transport is not None or max_concurrency is not None
        self._own = httpx.Client(follow_redirects=True, transport=transport) if private else None
        self._own_slots = threading.BoundedSemaphore(_ceiling(max_concurrency)) if private else None

    @contextmanager
    def _slot(self) -> Iterator[None]:
        slots = self._own_slots if self._own_slots is not None else _slots()
        slots.acquire()
        try:
            yield
        finally:
            slots.release()

    def fetch(self, locator: str) -> bytes:
        client = self._own if self._own is not None else _client()
        cause = ""
        for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
            retry_after = None
            try:
                # One attempt per slot, never the whole loop: a caller that is sleeping is
                # asking the origin for nothing, and a slot held through a backoff is an idle
                # slot (the reasoning `llm.py::_slot` states for the other transport).
                with self._slot():
                    response = client.get(locator, timeout=self._timeout)
            except httpx.HTTPError as exc:
                cause = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code not in RETRYABLE_STATUS:
                    if response.status_code >= 400:
                        # Including — especially — a 404: on this transport that is how a
                        # package says it does not carry an artifact, read on every
                        # registration. Waiting on it would tax the packages that are fine.
                        raise FetchError(
                            f"could not fetch artifact '{locator}': HTTP {response.status_code}"
                        )
                    return response.content
                cause = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After")
            self._backoff(attempt, retry_after=retry_after, locator=locator, cause=cause)
        raise FetchError(
            f"could not fetch artifact '{locator}': {cause} (after {MAX_FETCH_ATTEMPTS} attempts)"
        )

    def _backoff(self, attempt: int, retry_after: str | None, locator: str, cause: str) -> None:
        if attempt >= MAX_FETCH_ATTEMPTS:
            return  # the loop falls through to FetchError; no pointless final sleep
        delay = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        delay *= 0.5 + random.random() / 2  # jitter, so a fanned-out wave does not stampede
        if retry_after is not None:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass  # an HTTP-date Retry-After: the backoff schedule is a fine substitute
        logger.warning(
            "fetch attempt %d of '%s' failed (%s); retrying in %.1fs",
            attempt,
            locator,
            cause,
            delay,
        )
        self._sleep(delay)


class FilesystemFetcher:
    """Resolve locators as paths relative to a base directory (fixtures, local intake).

    A locator that resolves outside the base directory is refused (ADR-0035 §7). The
    locators discovery fetches are not written by whoever named the directory: a package
    declares its own artifact paths (`.learn/config.json` names the exercise files), so
    without this an unfamiliar package could name a file outside itself and have it hashed
    into the content identity and registered as an artifact. Symlinks are resolved before
    the check, which also keeps this fetcher honest about what the dev mount will serve —
    `StaticFiles` refuses to follow one out of its directory.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def fetch(self, locator: str) -> bytes:
        path = self._contained(locator)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise FetchError(f"could not read artifact '{locator}': {exc}") from exc

    def _contained(self, locator: str) -> Path:
        base = self._base_dir.resolve()
        path = (base / locator).resolve()
        if path != base and base not in path.parents:
            raise FetchError(f"artifact '{locator}' resolves outside '{self._base_dir.as_posix()}'")
        return path
