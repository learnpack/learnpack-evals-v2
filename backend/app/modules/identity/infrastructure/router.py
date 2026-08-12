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


class AutomatedIdentityResponse(BaseModel):
    """Present exactly when `kind == 'automated'` — the artifact and its lineage."""

    name: str
    version: str
    instrument_id: str


class AssessorResponse(BaseModel):
    assessor_id: UUID
    role: str
    email: str | None = None
    display_name: str | None = None
    kind: str = "human"
    automated: AutomatedIdentityResponse | None = None


@admin_router.get("/assessors", response_model=list[AssessorResponse])
def list_assessors(admin: AdminAssessor, identities: Identities) -> list[AssessorResponse]:
    """Every assessor, of both kinds. The assign picker filters `role == 'evaluator'`
    client-side; the assessors page groups by `kind`, which is why it is stated here —
    the two kinds are structurally different (ADR-0016) and a list that mixes them
    without saying so cannot be read."""
    return [
        AssessorResponse(
            assessor_id=a.assessor_id,
            role=a.role,
            email=a.email,
            display_name=a.display_name,
            kind=a.kind,
            automated=(
                AutomatedIdentityResponse(
                    name=a.automated.name,
                    version=a.automated.version,
                    instrument_id=a.automated.instrument_id,
                )
                if a.automated is not None
                else None
            ),
        )
        for a in identities.list_all_assessors()
    ]
