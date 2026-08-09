"""Locator → bytes fetchers — shared technical transport, no domain knowledge.

One implementation instead of per-module twins. Module isolation is untouched: each module
keeps its own Protocol port (structural typing) and its own failure *meaning* — a fetch
miss is a soft absent brief in the registry's intake, a failed extraction in profiling, a
refused registration in discovery. That translation happens at each module's boundary;
`FetchError` stays deliberately neutral.
"""

from pathlib import Path

import httpx


class FetchError(Exception):
    """The locator could not be fetched or read. What that *means* is the caller's
    boundary to decide — this exception carries no module's semantics."""


class HttpFetcher:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds

    def fetch(self, locator: str) -> bytes:
        try:
            response = httpx.get(locator, timeout=self._timeout, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FetchError(f"could not fetch artifact '{locator}': {exc}") from exc
        return response.content


class FilesystemFetcher:
    """Resolve locators as paths relative to a base directory (fixtures, local intake)."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def fetch(self, locator: str) -> bytes:
        path = self._base_dir / locator
        try:
            return path.read_bytes()
        except OSError as exc:
            raise FetchError(f"could not read artifact '{locator}': {exc}") from exc
