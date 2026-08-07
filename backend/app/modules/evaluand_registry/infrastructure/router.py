"""Admin HTTP adapter for Content Registry (08-code.md §7).

Translates request/response ↔ use case input/output. Domain entities never cross this
boundary — only DTOs (ARCHITECTURE.md §5).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.evaluand_registry.application import queries
from app.modules.evaluand_registry.application.dtos import (
    BriefDTO,
    ContentPackageDTO,
    ContentSnapshot,
    GeneratorArtifactDTO,
    GeneratorVersionDTO,
)
from app.modules.evaluand_registry.application.register_brief import (
    RegisterBrief,
    RegisterBriefCommand,
)
from app.modules.evaluand_registry.application.register_content_version import (
    BriefNotFound,
    DuplicateContent,
    RegisterContentVersion,
    RegisterContentVersionCommand,
    UnknownGeneratorVersion,
)
from app.modules.evaluand_registry.application.register_generator_artifact import (
    GeneratorVersionNotFound,
    RegisterGeneratorArtifact,
    RegisterGeneratorArtifactCommand,
)
from app.modules.evaluand_registry.application.register_generator_version import (
    DuplicateGeneratorVersion,
    RegisterGeneratorVersion,
    RegisterGeneratorVersionCommand,
)
from app.modules.evaluand_registry.domain.brief import InvalidBrief
from app.modules.evaluand_registry.domain.content import DEFAULT_VERSION, InvalidContent
from app.modules.evaluand_registry.domain.generator import (
    InvalidGeneratorArtifact,
    InvalidGeneratorVersion,
)
from app.modules.evaluand_registry.domain.package import InvalidPackage
from app.modules.evaluand_registry.infrastructure.brief_intake import LearnpackBriefIntake
from app.modules.evaluand_registry.infrastructure.fetchers import HttpArtifactFetcher
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorArtifactRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin/contents", tags=["content-registry"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class PackageArtifactInput(BaseModel):
    kind: str = Field(examples=["manifest"])
    locator: str
    format: str | None = None


class RegisterContentRequest(BaseModel):
    package_format: str = Field(examples=["LearnpackV1"])
    external_id: str
    consumable_url: str
    version: str = DEFAULT_VERSION
    artifacts: list[PackageArtifactInput] = Field(default_factory=list)
    brief_id: UUID | None = None
    generator_version_id: UUID | None = None
    edit_provenance: str = "unknown"


class ContentResponse(BaseModel):
    content_id: UUID
    package_format: str
    external_id: str
    version: str
    consumable_url: str
    brief_id: UUID | None
    generator_version_id: UUID | None
    edit_provenance: str

    @classmethod
    def from_snapshot(cls, snapshot: ContentSnapshot) -> "ContentResponse":
        return cls(
            content_id=snapshot.content_id,
            package_format=snapshot.package_format,
            external_id=snapshot.external_id,
            version=snapshot.version,
            consumable_url=snapshot.consumable_url,
            brief_id=snapshot.brief_id,
            generator_version_id=snapshot.generator_version_id,
            edit_provenance=snapshot.edit_provenance,
        )


class PackageArtifactResponse(BaseModel):
    kind: str
    locator: str
    format: str | None


class ContentPackageResponse(BaseModel):
    content_id: UUID
    package_format: str
    consumable_url: str
    artifacts: list[PackageArtifactResponse]

    @classmethod
    def from_dto(cls, dto: ContentPackageDTO) -> "ContentPackageResponse":
        return cls(
            content_id=dto.content_id,
            package_format=dto.package_format,
            consumable_url=dto.consumable_url,
            artifacts=[
                PackageArtifactResponse(kind=a.kind, locator=a.locator, format=a.format)
                for a in dto.artifacts
            ],
        )


def _snapshot_or_404(uow: UnitOfWork, content_id: UUID) -> ContentSnapshot:
    snapshot = queries.get_content_snapshot(SqlAlchemyContentRepository(uow.session), content_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
    return snapshot


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ContentResponse)
def register_content_version(
    request: RegisterContentRequest, admin: AdminAssessor, uow: Uow
) -> ContentResponse:
    use_case = RegisterContentVersion(
        contents=SqlAlchemyContentRepository(uow.session),
        briefs=SqlAlchemyBriefRepository(uow.session),
        generators=SqlAlchemyGeneratorVersionRepository(uow.session),
        publisher=uow.events,
        uow=uow,
        brief_intake=LearnpackBriefIntake(HttpArtifactFetcher()),
    )
    try:
        content = use_case(
            RegisterContentVersionCommand(
                package_format=request.package_format,
                external_id=request.external_id,
                consumable_url=request.consumable_url,
                version=request.version,
                artifacts=[a.model_dump() for a in request.artifacts],
                brief_id=request.brief_id,
                generator_version_id=request.generator_version_id,
                edit_provenance=request.edit_provenance,
            )
        )
    except DuplicateContent as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (
        InvalidContent,
        InvalidPackage,
        BriefNotFound,
        UnknownGeneratorVersion,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return ContentResponse.from_snapshot(_snapshot_or_404(uow, content.id))


@router.get("/{content_id}/package", response_model=ContentPackageResponse)
def get_content_package(content_id: UUID, admin: AdminAssessor, uow: Uow) -> ContentPackageResponse:
    dto = queries.get_content_package(SqlAlchemyContentRepository(uow.session), content_id)
    if dto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
    return ContentPackageResponse.from_dto(dto)


@router.get("", response_model=list[ContentResponse])
def list_contents(admin: AdminAssessor, uow: Uow) -> list[ContentResponse]:
    snapshots = queries.list_content_snapshots(SqlAlchemyContentRepository(uow.session))
    return [ContentResponse.from_snapshot(s) for s in snapshots]


@router.get("/{content_id}", response_model=ContentResponse)
def get_content(content_id: UUID, admin: AdminAssessor, uow: Uow) -> ContentResponse:
    return ContentResponse.from_snapshot(_snapshot_or_404(uow, content_id))


# ------------------------------------------------------- generators & briefs (13-code §3.2)

evaluand_router = APIRouter(prefix="/admin", tags=["evaluand-registry"])


class RegisterGeneratorRequest(BaseModel):
    name: str = Field(examples=["learnpack-generator"])
    version: str = Field(examples=["2.4.0"])
    # Free-form identity blob; fields get promoted to typed columns only when consumed.
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneratorVersionResponse(BaseModel):
    generator_version_id: UUID
    name: str
    version: str
    metadata: dict[str, Any]

    @classmethod
    def from_dto(cls, dto: GeneratorVersionDTO) -> "GeneratorVersionResponse":
        return cls(
            generator_version_id=dto.generator_version_id,
            name=dto.name,
            version=dto.version,
            metadata=dto.metadata,
        )


class RegisterBriefRequest(BaseModel):
    brief: str
    fields: dict[str, Any] = Field(default_factory=dict)


class BriefResponse(BaseModel):
    brief_id: UUID
    brief: str
    fields: dict[str, Any]

    @classmethod
    def from_dto(cls, dto: BriefDTO) -> "BriefResponse":
        return cls(brief_id=dto.brief_id, brief=dto.brief, fields=dto.fields)


class RegisterGeneratorArtifactRequest(BaseModel):
    kind: str = Field(examples=["prompt-template"])
    locator: str
    format: str | None = None


class GeneratorArtifactResponse(BaseModel):
    artifact_id: UUID
    generator_version_id: UUID
    kind: str
    locator: str
    format: str | None

    @classmethod
    def from_dto(cls, dto: GeneratorArtifactDTO) -> "GeneratorArtifactResponse":
        return cls(
            artifact_id=dto.artifact_id,
            generator_version_id=dto.generator_version_id,
            kind=dto.kind,
            locator=dto.locator,
            format=dto.format,
        )


@evaluand_router.post(
    "/generators", status_code=status.HTTP_201_CREATED, response_model=GeneratorVersionResponse
)
def register_generator(
    request: RegisterGeneratorRequest, admin: AdminAssessor, uow: Uow
) -> GeneratorVersionResponse:
    use_case = RegisterGeneratorVersion(
        generators=SqlAlchemyGeneratorVersionRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        generator = use_case(
            RegisterGeneratorVersionCommand(
                name=request.name, version=request.version, metadata=request.metadata
            )
        )
    except DuplicateGeneratorVersion as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidGeneratorVersion as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    dto = queries.get_generator_version(
        SqlAlchemyGeneratorVersionRepository(uow.session), generator.id
    )
    assert dto is not None  # just written in this transaction
    return GeneratorVersionResponse.from_dto(dto)


@evaluand_router.get("/generators", response_model=list[GeneratorVersionResponse])
def list_generators(admin: AdminAssessor, uow: Uow) -> list[GeneratorVersionResponse]:
    dtos = queries.list_generator_versions(SqlAlchemyGeneratorVersionRepository(uow.session))
    return [GeneratorVersionResponse.from_dto(d) for d in dtos]


@evaluand_router.post(
    "/generators/{generator_version_id}/artifacts",
    status_code=status.HTTP_201_CREATED,
    response_model=GeneratorArtifactResponse,
)
def register_generator_artifact(
    generator_version_id: UUID,
    request: RegisterGeneratorArtifactRequest,
    admin: AdminAssessor,
    uow: Uow,
) -> GeneratorArtifactResponse:
    use_case = RegisterGeneratorArtifact(
        generators=SqlAlchemyGeneratorVersionRepository(uow.session),
        artifacts=SqlAlchemyGeneratorArtifactRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        artifact = use_case(
            RegisterGeneratorArtifactCommand(
                generator_version_id=generator_version_id,
                kind=request.kind,
                locator=request.locator,
                format=request.format,
            )
        )
    except GeneratorVersionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="generator version not found"
        ) from exc
    except InvalidGeneratorArtifact as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return GeneratorArtifactResponse(
        artifact_id=artifact.id,
        generator_version_id=artifact.generator_version_id,
        kind=artifact.kind,
        locator=artifact.locator,
        format=artifact.format,
    )


@evaluand_router.get(
    "/generators/{generator_version_id}/artifacts",
    response_model=list[GeneratorArtifactResponse],
)
def list_generator_artifacts(
    generator_version_id: UUID, admin: AdminAssessor, uow: Uow
) -> list[GeneratorArtifactResponse]:
    dtos = queries.list_generator_artifacts(
        SqlAlchemyGeneratorArtifactRepository(uow.session), generator_version_id
    )
    return [GeneratorArtifactResponse.from_dto(d) for d in dtos]


@evaluand_router.post("/briefs", status_code=status.HTTP_201_CREATED, response_model=BriefResponse)
def register_brief(request: RegisterBriefRequest, admin: AdminAssessor, uow: Uow) -> BriefResponse:
    use_case = RegisterBrief(
        briefs=SqlAlchemyBriefRepository(uow.session), publisher=uow.events, uow=uow
    )
    try:
        brief = use_case(RegisterBriefCommand(brief=request.brief, fields=request.fields))
    except InvalidBrief as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return BriefResponse(brief_id=brief.id, brief=brief.brief, fields=brief.fields)


@evaluand_router.get("/briefs", response_model=list[BriefResponse])
def list_briefs(admin: AdminAssessor, uow: Uow) -> list[BriefResponse]:
    dtos = queries.list_briefs(SqlAlchemyBriefRepository(uow.session))
    return [BriefResponse.from_dto(d) for d in dtos]
