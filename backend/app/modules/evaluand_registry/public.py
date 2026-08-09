"""Public surface of the Evaluand Registry (ARCHITECTURE.md §3).

The **only** module in this package other modules may import. It re-exports the query DTOs
and the events, and provides `get_evaluand_registry_queries` for `Depends` — which builds the
repositories itself, so callers never name a concrete adapter.
"""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.evaluand_registry.application import queries as _queries
from app.modules.evaluand_registry.application.dtos import (
    BriefDTO,
    ContentPackageDTO,
    ContentSnapshot,
    GeneratorVersionDTO,
    PackageArtifactDTO,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.uow import UnitOfWork, get_uow

# Events this module publishes — the contract subscribers rely on.
CONTENT_VERSION_REGISTERED = "ContentVersionRegistered"
GENERATOR_VERSION_REGISTERED = "GeneratorVersionRegistered"
BRIEF_REGISTERED = "BriefRegistered"

__all__ = [
    "BRIEF_REGISTERED",
    "CONTENT_VERSION_REGISTERED",
    "GENERATOR_VERSION_REGISTERED",
    "BriefDTO",
    "ContentPackageDTO",
    "ContentSnapshot",
    "ContentVersionRegisteredFact",
    "EvaluandRegistryQueries",
    "GeneratorVersionDTO",
    "PackageArtifactDTO",
    "get_evaluand_registry_queries",
]


@dataclass(frozen=True)
class ContentVersionRegisteredFact:
    """The Published Language of `ContentVersionRegistered` — what subscribers may rely on.

    Artifacts stay out on purpose: consumers read the package via `get_content_package`.
    """

    content_id: UUID
    package_format: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ContentVersionRegisteredFact":
        return cls(
            content_id=UUID(payload["contentId"]),
            # Old rows in `events` carry the pre-rename key; both replay fine.
            package_format=payload.get("packageFormat") or payload["generatingSystem"],
        )


class EvaluandRegistryQueries:
    """Read-only contract of the Evaluand Registry."""

    def __init__(self, session: Session) -> None:
        self._contents = SqlAlchemyContentRepository(session)
        self._generators = SqlAlchemyGeneratorVersionRepository(session)
        self._briefs = SqlAlchemyBriefRepository(session)

    def get_content_snapshot(self, content_id: UUID) -> ContentSnapshot | None:
        return _queries.get_content_snapshot(self._contents, content_id)

    def get_content_package(self, content_id: UUID) -> ContentPackageDTO | None:
        return _queries.get_content_package(self._contents, content_id)

    def list_content_snapshots(self) -> list[ContentSnapshot]:
        return _queries.list_content_snapshots(self._contents)

    def get_generator_version(self, generator_version_id: UUID) -> GeneratorVersionDTO | None:
        return _queries.get_generator_version(self._generators, generator_version_id)

    def get_available_contents(
        self,
        package_format: str | None = None,
        brief_ids: list[UUID] | None = None,
        generator_known: bool = False,
    ) -> list[ContentSnapshot]:
        return _queries.get_available_contents(
            self._contents,
            package_format=package_format,
            brief_ids=brief_ids,
            generator_known=generator_known,
        )

    def get_brief(self, brief_id: UUID) -> BriefDTO | None:
        return _queries.get_brief(self._briefs, brief_id)

    def list_briefs(self) -> list[BriefDTO]:
        return _queries.list_briefs(self._briefs)


def get_evaluand_registry_queries(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> EvaluandRegistryQueries:
    return EvaluandRegistryQueries(uow.session)
