"""Public surface of Content Profiling (ARCHITECTURE.md §3).

What crosses this boundary: the events (`ContentProfiled` is the pivotal fact Evaluation
will react to) and the read side — `get_profile` returns the self-contained, cited
snapshot (ADR-0009), `get_capabilities` the supply side of the demand/supply matching.
"""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.content_profiling.application import queries as _queries
from app.modules.content_profiling.application.dtos import (
    CapabilitiesSnapshot,
    ContentProfileSnapshot,
    ProfileEntrySnapshot,
    ProfileExtraSnapshot,
)
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.repository import (
    SqlAlchemyAcceptanceRepository,
    SqlAlchemyProfileRepository,
)
from app.platform.uow import UnitOfWork, get_uow

# Events this module publishes — the contract subscribers rely on.
CONTENT_PROFILED = "ContentProfiled"
CONTENT_PROFILING_FAILED = "ContentProfilingFailed"
EXTRACTION_ACCEPTED = "ExtractionAccepted"

__all__ = [
    "CONTENT_PROFILED",
    "CONTENT_PROFILING_FAILED",
    "EXTRACTION_ACCEPTED",
    "CapabilitiesSnapshot",
    "ContentProfiledFact",
    "ContentProfileSnapshot",
    "ContentProfilingQueries",
    "ProfileEntrySnapshot",
    "ProfileExtraSnapshot",
    "get_content_profiling_queries",
]


@dataclass(frozen=True)
class ContentProfiledFact:
    """The Published Language of `ContentProfiled` — coordinates only; subscribers read
    the entries through `get_profile` (same convention as the registry's events)."""

    profile_id: UUID
    content_id: UUID
    package_format: str
    adapter_version: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ContentProfiledFact":
        return cls(
            profile_id=UUID(payload["profileId"]),
            content_id=UUID(payload["contentId"]),
            package_format=payload["packageFormat"],
            adapter_version=payload["adapterVersion"],
        )


class ContentProfilingQueries:
    """Read-only contract of Content Profiling."""

    def __init__(self, session: Session) -> None:
        self._profiles = SqlAlchemyProfileRepository(session)
        self._acceptances = SqlAlchemyAcceptanceRepository(session)

    def get_profile(
        self, content_id: UUID, adapter_version: str | None = None
    ) -> ContentProfileSnapshot | None:
        return _queries.get_profile(self._profiles, content_id, adapter_version)

    def get_declared_data(self, content_id: UUID) -> dict[str, str]:
        """`{data_requirement_id: provenance}` over the most recent **ok** profile, or {}."""
        return _queries.get_declared_data(self._profiles, content_id)

    def get_declared_values(
        self, content_id: UUID, requirement_ids: Collection[str]
    ) -> dict[str, Any]:
        """What the content declares for those ids, readable as prose (ADR-0057)."""
        return _queries.get_declared_values(self._profiles, content_id, requirement_ids)

    def list_profiles(self) -> list[ContentProfileSnapshot]:
        return _queries.list_profiles(self._profiles)

    def get_capabilities(self, package_format: str) -> CapabilitiesSnapshot | None:
        return _queries.get_capabilities(ADAPTERS_BY_FORMAT, self._acceptances, package_format)

    def list_capabilities(self) -> list[CapabilitiesSnapshot]:
        return _queries.list_capabilities(ADAPTERS_BY_FORMAT, self._acceptances)


def get_content_profiling_queries(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> ContentProfilingQueries:
    return ContentProfilingQueries(uow.session)
