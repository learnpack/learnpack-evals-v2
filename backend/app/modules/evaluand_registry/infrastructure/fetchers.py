"""Artifact fetchers for the brief intake: locator → bytes (ADR-0022).

Deliberate twin of profiling's fetchers, not an import: modules do not cross each other's
infrastructure (test_architecture), and intake failures are registry-local — soft by design.
"""

from pathlib import Path

import httpx


class BriefIntakeError(Exception):
    """The syllabus artifact could not be fetched or read (soft failure upstream)."""


class HttpArtifactFetcher:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds

    def fetch(self, locator: str) -> bytes:
        try:
            response = httpx.get(locator, timeout=self._timeout, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BriefIntakeError(f"could not fetch artifact '{locator}': {exc}") from exc
        return response.content


class FilesystemArtifactFetcher:
    """Resolve locators as paths relative to a base directory (fixtures, local intake)."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def fetch(self, locator: str) -> bytes:
        path = self._base_dir / locator
        try:
            return path.read_bytes()
        except OSError as exc:
            raise BriefIntakeError(f"could not read artifact '{locator}': {exc}") from exc
