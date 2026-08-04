"""Public surface of Content Registry (ARCHITECTURE.md §3).

The **only** module in this package other modules may import. It re-exports the query DTOs
and the events, and provides `get_evaluand_registry_queries` for `Depends` — which builds the
repositories itself, so callers never name a concrete adapter.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.evaluand_registry.application import queries as _queries
from app.modules.evaluand_registry.application.dtos import ContentSnapshot, MetadataEntryDTO
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyContentRepository,
    SqlAlchemyMetadataSchemaRepository,
)
from app.platform.uow import UnitOfWork, get_uow

# Events this module publishes — the contract subscribers rely on.
CONTENT_VERSION_REGISTERED = "ContentVersionRegistered"
CONTENT_METADATA_UPDATED = "ContentMetadataUpdated"

__all__ = [
    "CONTENT_METADATA_UPDATED",
    "CONTENT_VERSION_REGISTERED",
    "EvaluandRegistryQueries",
    "ContentSnapshot",
    "MetadataEntryDTO",
    "get_evaluand_registry_queries",
]


class EvaluandRegistryQueries:
    """Read-only contract of Content Registry (`getContentSnapshot`, `getContentMetadata`)."""

    def __init__(self, session: Session) -> None:
        self._contents = SqlAlchemyContentRepository(session)
        self._schemas = SqlAlchemyMetadataSchemaRepository(session)

    def get_content_snapshot(self, content_id: UUID) -> ContentSnapshot | None:
        return _queries.get_content_snapshot(self._contents, self._schemas, content_id)

    def get_content_metadata(self, content_id: UUID) -> list[MetadataEntryDTO] | None:
        return _queries.get_content_metadata(self._contents, self._schemas, content_id)

    def list_content_snapshots(self) -> list[ContentSnapshot]:
        return _queries.list_content_snapshots(self._contents, self._schemas)


def get_evaluand_registry_queries(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> EvaluandRegistryQueries:
    return EvaluandRegistryQueries(uow.session)
