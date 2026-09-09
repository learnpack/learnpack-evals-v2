"""Gateways: the only place Orchestration imports another module's public surface.

A use case needs the courses a dataset version holds before it can open a campaign over them,
and needs to know whether there is a person behind an id before it hands them a course. The
application layer may not see another module (ARCHITECTURE.md §3), so each of those questions
is a port beside the use case and an adapter here.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.datasets.public import DatasetsQueries
from app.modules.identity.public import IdentityQueries
from app.modules.orchestration.application.ports import Assessee


class DatasetsGateway:
    def __init__(self, session: Session) -> None:
        self._queries = DatasetsQueries(session)

    def get_version_members(self, version_id: UUID) -> list[UUID] | None:
        version = self._queries.get_version(version_id)
        return None if version is None else list(version.content_ids)


class AssessorsGateway:
    """The roster, reduced to the question the assignment path asks of it (ADR-0067).

    The translation is the point: `kind` and `status` are Identity's words for what somebody
    is, and what Orchestration needs to know is only whether there is a person there and
    whether they are still here. The role is read and dropped — see `Assessee`.
    """

    def __init__(self, session: Session) -> None:
        self._queries = IdentityQueries(session)

    def get_assessee(self, assessor_id: UUID) -> Assessee | None:
        assessor = self._queries.get_assessor(assessor_id)
        if assessor is None:
            return None
        return Assessee(is_human=assessor.kind == "human", is_active=assessor.is_active)
