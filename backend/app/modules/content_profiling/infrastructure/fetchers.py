"""PackageFetcherPort implementations: the shared transport, profiling's semantics.

HTTP for real packages, filesystem for the frozen fixtures — same port, so the adapter
cannot tell them apart (the point: extraction is specified by fixtures, design 10). The
byte-moving lives in `app.shared.infrastructure.fetchers`; what belongs HERE is the
boundary translation: a fetch miss is a failed extraction (`ExtractionError`).
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from app.modules.content_profiling.domain.profile import ExtractionError
from app.platform.concurrency import all_at_once
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher, HttpFetcher


class HttpPackageFetcher:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._fetcher = HttpFetcher(timeout_seconds)

    def fetch(self, locator: str) -> bytes:
        try:
            return self._fetcher.fetch(locator)
        except FetchError as exc:
            raise ExtractionError(str(exc)) from exc

    def fetch_all(self, locators: Sequence[str]) -> Mapping[str, bytes]:
        """All at once. Nothing is capped here: what bounds the requests in flight is the gate
        at the shared transport (`HTTP_MAX_CONCURRENCY`), which sees a discovery reading one
        package and a profiling run reading another as the same requests to whoever is serving
        them. A miss still fails the extraction, at the first locator that fails in the order
        it was asked for — whatever finished first."""
        wanted = list(dict.fromkeys(locators))
        return dict(zip(wanted, all_at_once(self.fetch, wanted), strict=True))


class FilesystemPackageFetcher:
    """Resolve locators as paths relative to a base directory (fixtures, local intake)."""

    def __init__(self, base_dir: Path) -> None:
        self._fetcher = FilesystemFetcher(base_dir)

    def fetch(self, locator: str) -> bytes:
        try:
            return self._fetcher.fetch(locator)
        except FetchError as exc:
            raise ExtractionError(str(exc)) from exc

    def fetch_all(self, locators: Sequence[str]) -> Mapping[str, bytes]:
        """One at a time: a local read has nothing to wait for, so a thread per file would buy
        a scheduler and no time at all."""
        return {locator: self.fetch(locator) for locator in locators}
