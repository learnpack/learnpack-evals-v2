"""Locator → bytes fetchers — shared technical transport, no domain knowledge.

One implementation instead of per-module twins. Module isolation is untouched: each module
keeps its own Protocol port (structural typing) and its own failure *meaning* — a fetch
miss is a soft absent brief in the registry's intake, a failed extraction in profiling, a
refused registration in discovery. That translation happens at each module's boundary;
`FetchError` stays deliberately neutral.
"""

import threading
from pathlib import Path

import httpx


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
_client_lock = threading.Lock()


def _client() -> httpx.Client:
    global _shared_client
    with _client_lock:
        if _shared_client is None:
            _shared_client = httpx.Client(follow_redirects=True)
        return _shared_client


class HttpFetcher:
    """Artifacts over http, on a connection that outlives the fetch.

    The timeout stays per instance and travels with each request — it was the only thing
    that told one fetcher from another, and it does not justify a client of its own.
    """

    def __init__(
        self, timeout_seconds: float = 10.0, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._timeout = timeout_seconds
        # A caller that brings its own transport gets its own client: a test must not
        # inherit connections from another, nor leave any behind in the shared one.
        self._own = (
            httpx.Client(follow_redirects=True, transport=transport)
            if transport is not None
            else None
        )

    def fetch(self, locator: str) -> bytes:
        client = self._own if self._own is not None else _client()
        try:
            response = client.get(locator, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(f"could not fetch artifact '{locator}': {exc}") from exc
        return response.content


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
