"""Admin HTTP adapter for Content Registry (08-code.md §7).

Translates request/response ↔ use case input/output. Domain entities never cross this
boundary — only DTOs (ARCHITECTURE.md §5).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.content_registry.application import queries
from app.modules.content_registry.application.dtos import ContentSnapshot
from app.modules.content_registry.application.register_content import (
    DuplicateContent,
    RegisterContent,
    RegisterContentCommand,
    UnknownGeneratingSystem,
)
from app.modules.content_registry.application.update_content_metadata import (
    ContentNotFound,
    UpdateContentMetadata,
    UpdateContentMetadataCommand,
)
from app.modules.content_registry.domain.content import DEFAULT_VERSION, InvalidContent
from app.modules.content_registry.domain.metadata import InvalidMetadata
from app.modules.content_registry.infrastructure.repository import (
    SqlAlchemyContentRepository,
    SqlAlchemyMetadataSchemaRepository,
)
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin/contents", tags=["content-registry"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class RegisterContentRequest(BaseModel):
    generating_system: str = Field(examples=["LearnpackV1"])
    external_id: str
    consumable_url: str
    version: str = DEFAULT_VERSION
    # Open collection validated against the MetadataSchema, not against this model (ADR-0001).
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateMetadataRequest(BaseModel):
    metadata: dict[str, Any]


class MetadataEntryResponse(BaseModel):
    key: str
    value: Any
    value_type: str


class ContentResponse(BaseModel):
    content_id: UUID
    generating_system: str
    external_id: str
    version: str
    consumable_url: str
    metadata: list[MetadataEntryResponse]

    @classmethod
    def from_snapshot(cls, snapshot: ContentSnapshot) -> "ContentResponse":
        return cls(
            content_id=snapshot.content_id,
            generating_system=snapshot.generating_system,
            external_id=snapshot.external_id,
            version=snapshot.version,
            consumable_url=snapshot.consumable_url,
            metadata=[
                MetadataEntryResponse(key=e.key, value=e.value, value_type=e.value_type)
                for e in snapshot.metadata
            ],
        )


def _snapshot_or_404(uow: UnitOfWork, content_id: UUID) -> ContentSnapshot:
    snapshot = queries.get_content_snapshot(
        SqlAlchemyContentRepository(uow.session),
        SqlAlchemyMetadataSchemaRepository(uow.session),
        content_id,
    )
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
    return snapshot


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ContentResponse)
def register_content(
    request: RegisterContentRequest, admin: AdminAssessor, uow: Uow
) -> ContentResponse:
    use_case = RegisterContent(
        contents=SqlAlchemyContentRepository(uow.session),
        schemas=SqlAlchemyMetadataSchemaRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        content = use_case(
            RegisterContentCommand(
                generating_system=request.generating_system,
                external_id=request.external_id,
                consumable_url=request.consumable_url,
                version=request.version,
                metadata=request.metadata,
            )
        )
    except DuplicateContent as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidMetadata as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors
        ) from exc
    except (InvalidContent, UnknownGeneratingSystem) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return ContentResponse.from_snapshot(_snapshot_or_404(uow, content.id))


@router.patch("/{content_id}/metadata", response_model=ContentResponse)
def update_content_metadata(
    content_id: UUID, request: UpdateMetadataRequest, admin: AdminAssessor, uow: Uow
) -> ContentResponse:
    use_case = UpdateContentMetadata(
        contents=SqlAlchemyContentRepository(uow.session),
        schemas=SqlAlchemyMetadataSchemaRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        use_case(UpdateContentMetadataCommand(content_id=content_id, metadata=request.metadata))
    except ContentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="content not found"
        ) from exc
    except InvalidMetadata as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors
        ) from exc
    except UnknownGeneratingSystem as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return ContentResponse.from_snapshot(_snapshot_or_404(uow, content_id))


@router.get("", response_model=list[ContentResponse])
def list_contents(admin: AdminAssessor, uow: Uow) -> list[ContentResponse]:
    snapshots = queries.list_content_snapshots(
        SqlAlchemyContentRepository(uow.session),
        SqlAlchemyMetadataSchemaRepository(uow.session),
    )
    return [ContentResponse.from_snapshot(s) for s in snapshots]


@router.get("/{content_id}", response_model=ContentResponse)
def get_content(content_id: UUID, admin: AdminAssessor, uow: Uow) -> ContentResponse:
    return ContentResponse.from_snapshot(_snapshot_or_404(uow, content_id))
