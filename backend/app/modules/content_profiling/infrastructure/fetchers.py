"""PackageFetcherPort implementations: the shared transport, profiling's semantics.

HTTP for real packages, filesystem for the frozen fixtures — same port, so the adapter
cannot tell them apart (the point: extraction is specified by fixtures, design 10). The
byte-moving lives in `app.shared.infrastructure.fetchers`; what belongs HERE is the
boundary translation: a fetch miss is a failed extraction (`ExtractionError`).
"""

from pathlib import Path

from app.modules.content_profiling.domain.profile import ExtractionError
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher, HttpFetcher


class HttpPackageFetcher:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._fetcher = HttpFetcher(timeout_seconds)

    def fetch(self, locator: str) -> bytes:
        try:
            return self._fetcher.fetch(locator)
        except FetchError as exc:
            raise ExtractionError(str(exc)) from exc


class FilesystemPackageFetcher:
    """Resolve locators as paths relative to a base directory (fixtures, local intake)."""

    def __init__(self, base_dir: Path) -> None:
        self._fetcher = FilesystemFetcher(base_dir)

    def fetch(self, locator: str) -> bytes:
        try:
            return self._fetcher.fetch(locator)
        except FetchError as exc:
            raise ExtractionError(str(exc)) from exc
