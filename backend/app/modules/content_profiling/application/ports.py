"""Ports of Content Profiling (hexagonal: defined here, implemented in infrastructure).

The extraction adapter itself is a port implementation, not an aggregate (design 12):
versioned, with capabilities declared against the `data_requirements` namespace, and
testable with frozen fixtures — the investment of this context goes to fixtures, not
model.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from uuid import UUID

from app.modules.content_profiling.application.dtos import PackageDTO
from app.modules.content_profiling.domain.profile import ContentProfile, ProfileEntry, ProfileExtra


class PackageFetcherPort(Protocol):
    """Resolve an artifact locator to its bytes (HTTP in production, filesystem in tests).

    `fetch_all` is how an adapter says a group of reads is independent of each other — the
    lesson bodies, say, which it selects by kind and never opens to find one another. It says
    nothing about how they are produced: over http they go out together, off a filesystem they
    are still a loop, because a local read has nothing to wait for. Same arrangement as the
    registry's `PackageRoot` on the discovery side.
    """

    def fetch(self, locator: str) -> bytes: ...

    def fetch_all(self, locators: Sequence[str]) -> Mapping[str, bytes]: ...


class ExtractionAdapterPort(Protocol):
    """One extraction adapter for one package format, versioned (design 13 §3.4).

    `extract` is deterministic and never infers (ADR-0009): it returns one entry per
    declared capability — `absent` when the data is not there — plus optional extras.
    It raises `ExtractionError` when the package cannot be read at all.
    """

    @property
    def package_format(self) -> str: ...

    @property
    def adapter_version(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[str]: ...

    def extract(
        self, package: PackageDTO, fetcher: PackageFetcherPort
    ) -> tuple[tuple[ProfileEntry, ...], tuple[ProfileExtra, ...]]: ...


class ContentGatewayPort(Protocol):
    """Read the evaluand from the registry (implemented over its public surface)."""

    def get_package(self, content_id: UUID) -> PackageDTO | None: ...

    def list_content_ids(self, package_format: str) -> list[UUID]: ...


class DataRequirementNamespacePort(Protocol):
    """The canonical demand-side namespace minted by Evaluation Design (ADR-0014).

    Each id comes with its declared value domain (ADR-0020) — mandatory there, so the
    key set IS the namespace and the shapes travel with it in one read.
    """

    def value_domains(self) -> Mapping[str, dict[str, Any]]: ...


class ProfileRepositoryPort(Protocol):
    def insert(self, profile: ContentProfile) -> bool:
        """Idempotent: False when (content_id, adapter_version) already exists (ADR-0003)."""
        ...

    def get_status(self, content_id: UUID, adapter_version: str) -> str | None: ...

    def delete_failed(self, content_id: UUID, adapter_version: str) -> bool:
        """Remove a failed profile so the manual path can retry; never touches `ok`."""
        ...

    def get(self, content_id: UUID, adapter_version: str | None) -> ContentProfile | None:
        """Without a version: the most recent ok profile, else the most recent at all —
        so the workbench can still show what broke."""
        ...

    def list_all(self) -> list[ContentProfile]: ...


class AcceptanceRepositoryPort(Protocol):
    def accept(self, package_format: str, adapter_version: str, accepted_by: UUID) -> bool:
        """Idempotent: False when the acceptance already exists."""
        ...

    def is_accepted(self, package_format: str, adapter_version: str) -> bool: ...
