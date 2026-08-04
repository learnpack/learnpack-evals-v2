"""PackageFetcherPort implementations: locator → bytes.

HTTP for real packages, filesystem for the frozen fixtures — same port, so the adapter
cannot tell them apart (the point: extraction is specified by fixtures, design 10).
"""

from pathlib import Path

import httpx

from app.modules.content_profiling.domain.profile import ExtractionError


class HttpPackageFetcher:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds

    def fetch(self, locator: str) -> bytes:
        try:
            response = httpx.get(locator, timeout=self._timeout, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExtractionError(f"could not fetch artifact '{locator}': {exc}") from exc
        return response.content


class FilesystemPackageFetcher:
    """Resolve locators as paths relative to a base directory (fixtures, local intake)."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def fetch(self, locator: str) -> bytes:
        path = self._base_dir / locator
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ExtractionError(f"could not read artifact '{locator}': {exc}") from exc
