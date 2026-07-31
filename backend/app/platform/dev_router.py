"""Dev-only endpoints, available exclusively under `AUTH_MODE=local` (ADR-0008).

The local sign-in screen needs to know who it can sign in as. Reading it from the database
—instead of hardcoding the seeded users in the frontend— keeps one source of truth: whoever
you add with `app.cli seed-demo` (or by signing in once) shows up in the picker.

The router is always registered and refuses to answer outside local mode, so the guard is
exercised by the test suite without rebuilding the app.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.modules.identity.public import IdentityQueries, get_identity_queries

router = APIRouter(prefix="/dev", tags=["dev"])


class DevIdentityResponse(BaseModel):
    email: str
    display_name: str | None = None
    role: str


@router.get("/identities", response_model=list[DevIdentityResponse])
def list_dev_identities(
    queries: Annotated[IdentityQueries, Depends(get_identity_queries)],
) -> list[DevIdentityResponse]:
    """Who you can sign in as locally. 404 in any other auth mode."""
    if not get_settings().is_local_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    return [
        DevIdentityResponse(email=a.email, display_name=a.display_name, role=a.role)
        for a in queries.list_all_assessors()
        if a.email
    ]
