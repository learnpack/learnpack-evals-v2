"""Gateways: the only place Orchestration imports another module's public surface.

The use case needs the courses a dataset version holds before it can open a campaign over
them, and the application layer may not see another module (ARCHITECTURE.md §3). The port
lives beside the use case; this is its adapter.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.datasets.public import DatasetsQueries


class DatasetsGateway:
    def __init__(self, session: Session) -> None:
        self._queries = DatasetsQueries(session)

    def get_version_members(self, version_id: UUID) -> list[UUID] | None:
        version = self._queries.get_version(version_id)
        return None if version is None else list(version.content_ids)
