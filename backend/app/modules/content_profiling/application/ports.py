"""Ports of Content Profiling (hexagonal: defined here, implemented in infrastructure).

The extraction adapter itself is a port implementation, not an aggregate (design 12):
versioned, with capabilities declared against the `data_requirements` namespace, and
testable with frozen fixtures — the investment of this context goes to fixtures, not
model.
"""

from typing import Protocol
from uuid import UUID

from app.modules.content_profiling.application.dtos import PackageDTO
from app.modules.content_profiling.domain.profile import ContentProfile, ProfileEntry, ProfileExtra


class PackageFetcherPort(Protocol):
    """Resolve an artifact locator to its bytes (HTTP in production, filesystem in tests)."""

    def fetch(self, locator: str) -> bytes: ...


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
    """The canonical demand-side namespace minted by Evaluation Design (ADR-0014)."""

    def canonical_ids(self) -> frozenset[str]: ...


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
