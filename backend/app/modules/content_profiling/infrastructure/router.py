"""Read-only admin endpoints of Content Profiling — the designer's workbench feed
(ADR-0012). Commands stay in the CLI: profiling, accepting and re-profiling are
deliberate acts, not page buttons, in the first increment.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.content_profiling.application.dtos import (
    CapabilitiesSnapshot,
    ContentProfileSnapshot,
)
from app.modules.content_profiling.public import ContentProfilingQueries
from app.modules.evaluand_registry.public import EvaluandRegistryQueries
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin", tags=["content-profiling"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class ProfileEntryResponse(BaseModel):
    data_requirement_id: str
    provenance: str
    value: Any = None
    quote: str | None = None
    locator: dict[str, Any] | None = None


class ProfileExtraResponse(BaseModel):
    name: str
    value: Any = None
    quote: str | None = None
    locator: dict[str, Any] | None = None


class ProfileResponse(BaseModel):
    profile_id: UUID
    content_id: UUID
    external_id: str | None  # composed from the registry (ADR-0006 style)
    content_version: str | None
    package_format: str
    adapter_version: str
    status: str
    error: str | None
    profiled_at: str | None
    entries: list[ProfileEntryResponse]
    extras: list[ProfileExtraResponse]

    @classmethod
    def from_snapshot(
        cls, snapshot: ContentProfileSnapshot, content: tuple[str, str] | None
    ) -> "ProfileResponse":
        return cls(
            profile_id=snapshot.profile_id,
            content_id=snapshot.content_id,
            external_id=content[0] if content else None,
            content_version=content[1] if content else None,
            package_format=snapshot.package_format,
            adapter_version=snapshot.adapter_version,
            status=snapshot.status,
            error=snapshot.error,
            profiled_at=snapshot.profiled_at.isoformat() if snapshot.profiled_at else None,
            entries=[
                ProfileEntryResponse(
                    data_requirement_id=entry.data_requirement_id,
                    provenance=entry.provenance,
                    value=entry.value,
                    quote=entry.quote,
                    locator=entry.locator,
                )
                for entry in snapshot.entries
            ],
            extras=[
                ProfileExtraResponse(
                    name=extra.name, value=extra.value, quote=extra.quote, locator=extra.locator
                )
                for extra in snapshot.extras
            ],
        )


class CapabilitiesResponse(BaseModel):
    package_format: str
    adapter_version: str
    capabilities: list[str]
    accepted: bool

    @classmethod
    def from_snapshot(cls, snapshot: CapabilitiesSnapshot) -> "CapabilitiesResponse":
        return cls(
            package_format=snapshot.package_format,
            adapter_version=snapshot.adapter_version,
            capabilities=list(snapshot.capabilities),
            accepted=snapshot.accepted,
        )


def _content_identities(uow: UnitOfWork) -> dict[UUID, tuple[str, str]]:
    return {
        snapshot.content_id: (snapshot.external_id, snapshot.version)
        for snapshot in EvaluandRegistryQueries(uow.session).list_content_snapshots()
    }


@router.get("/profiles", response_model=list[ProfileResponse])
def list_profiles(admin: AdminAssessor, uow: Uow) -> list[ProfileResponse]:
    contents = _content_identities(uow)
    return [
        ProfileResponse.from_snapshot(snapshot, contents.get(snapshot.content_id))
        for snapshot in ContentProfilingQueries(uow.session).list_profiles()
    ]


@router.get("/contents/{content_id}/profile", response_model=ProfileResponse)
def get_content_profile(
    content_id: UUID,
    admin: AdminAssessor,
    uow: Uow,
    adapter_version: str | None = None,
) -> ProfileResponse:
    snapshot = ContentProfilingQueries(uow.session).get_profile(content_id, adapter_version)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"content {content_id} has no profile",
        )
    return ProfileResponse.from_snapshot(
        snapshot, _content_identities(uow).get(snapshot.content_id)
    )


@router.get("/profiling/capabilities", response_model=list[CapabilitiesResponse])
def list_capabilities(admin: AdminAssessor, uow: Uow) -> list[CapabilitiesResponse]:
    return [
        CapabilitiesResponse.from_snapshot(snapshot)
        for snapshot in ContentProfilingQueries(uow.session).list_capabilities()
    ]
