"""Ports required by identity's use cases. Implemented in infrastructure."""

from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.assessor import Assessor


class AssessorRepositoryPort(Protocol):
    def get_by_clerk_user_id(self, clerk_user_id: str) -> Assessor | None: ...

    def get_by_id(self, assessor_id: UUID) -> Assessor | None: ...

    def get_by_email(self, email: str) -> Assessor | None: ...

    def add(self, assessor: Assessor) -> None: ...

    def update(self, assessor: Assessor) -> None: ...
