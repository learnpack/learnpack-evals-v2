"""HTTP adapter for Identity: the admin's read-only roster of assessors.

The only write path into Identity is the login upsert (`ResolveAssessor`, ADR-0004); role
changes stay in the CLI (`app.cli set-role`). This router is purely a query surface so the
admin console can pick who to assign (08-code.md §7).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.identity.public import IdentityQueries, get_identity_queries
from app.platform.security import AdminAssessor

admin_router = APIRouter(prefix="/admin", tags=["identity-admin"])

Identities = Annotated[IdentityQueries, Depends(get_identity_queries)]


class AssessorResponse(BaseModel):
    assessor_id: UUID
    role: str
    email: str | None = None
    display_name: str | None = None


@admin_router.get("/assessors", response_model=list[AssessorResponse])
def list_assessors(admin: AdminAssessor, identities: Identities) -> list[AssessorResponse]:
    """Every assessor. The assign picker filters `role == 'evaluator'` client-side."""
    return [
        AssessorResponse(
            assessor_id=a.assessor_id,
            role=a.role,
            email=a.email,
            display_name=a.display_name,
        )
        for a in identities.list_all_assessors()
    ]
