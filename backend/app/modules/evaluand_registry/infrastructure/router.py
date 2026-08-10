"""Admin HTTP adapter for Content Registry (08-code.md §7).

Translates request/response ↔ use case input/output. Domain entities never cross this
boundary — only DTOs (ARCHITECTURE.md §5).
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.modules.evaluand_registry.application import queries
from app.modules.evaluand_registry.application.attribute_generator import (
    AttributeGenerator,
    AttributeGeneratorCommand,
    ContentNotFound,
)
from app.modules.evaluand_registry.application.dtos import (
    BriefDTO,
    ContentPackageDTO,
    ContentSnapshot,
    GeneratorDTO,
    GeneratorVersionDTO,
)
from app.modules.evaluand_registry.application.ports import PackageDiscoveryError
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
from app.modules.evaluand_registry.application.register_generator import (
    DuplicateGenerator,
    RegisterGenerator,
    RegisterGeneratorCommand,
    SimilarGeneratorExists,
)
from app.modules.evaluand_registry.application.register_generator_version import (
    DuplicateGeneratorVersion,
    RegisterGeneratorVersion,
    RegisterGeneratorVersionCommand,
    UnknownGenerator,
)
from app.modules.evaluand_registry.application.register_package_from_source import (
    RegisterPackageFromSource,
    RegisterPackageFromSourceCommand,
)
from app.modules.evaluand_registry.domain.brief import InvalidBrief
from app.modules.evaluand_registry.domain.content import (
    DEFAULT_VERSION,
    GeneratorAlreadyAttributed,
    InvalidContent,
)
from app.modules.evaluand_registry.domain.generator import (
    InvalidGenerator,
    InvalidGeneratorVersion,
)
from app.modules.evaluand_registry.domain.package import InvalidPackage
from app.modules.evaluand_registry.infrastructure.brief_intake import PackageBriefIntake
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    DISCOVERIES_BY_FORMAT,
    HttpPackageRoot,
    PackageDiscovery,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow
from app.shared.infrastructure.fetchers import HttpFetcher

router = APIRouter(prefix="/admin/contents", tags=["content-registry"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]


class PackageArtifactInput(BaseModel):
    kind: str = Field(examples=["manifest"])
    locator: str
    format: str | None = None


class RegisterContentRequest(BaseModel):
    package_format: str = Field(examples=["LearnpackV1"])
    external_id: str
    # Optional, unlike the generator key below (ADR-0028): an absent URL declares that no
    # deployed instance exists, which is the honest default for a package nobody hosts.
    consumable_url: str | None = None
    version: str = DEFAULT_VERSION
    artifacts: list[PackageArtifactInput] = Field(default_factory=list)
    brief_id: UUID | None = None
    # Required, and null is a legal value: the key must be present (ADR-0024, applying
    # ADR-0020's "nullable is not optionality"). Null declares `unknown`.
    generator_version_id: UUID | None = Field(...)
    edit_provenance: str = "unknown"


class ContentResponse(BaseModel):
    content_id: UUID
    package_format: str
    external_id: str
    version: str
    # Always present in the JSON, null when no deployed instance is declared (ADR-0028).
    consumable_url: str | None
    brief_id: UUID | None
    generator_version_id: UUID | None
    edit_provenance: str
    # Null unless the generator was attributed after registration (ADR-0024).
    generator_attributed_by: UUID | None = None
    generator_attributed_at: str | None = None

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
            generator_attributed_by=snapshot.generator_attributed_by,
            generator_attributed_at=(
                snapshot.generator_attributed_at.isoformat()
                if snapshot.generator_attributed_at
                else None
            ),
        )


class RegisterBySourceRequest(BaseModel):
    package_format: str = Field(examples=["LearnpackV1"])
    # The API takes http(s) sources only — local directories are the CLI's business.
    source_locator: str = Field(examples=["https://my-course.learn-pack.com"])
    # Required, and null is a legal value: the key must be present (ADR-0024). Null
    # declares `unknown`.
    generator_version_id: UUID | None = Field(...)
    edit_provenance: str = "unknown"
    version: str = DEFAULT_VERSION


class RegisterBySourceResponse(BaseModel):
    content: ContentResponse
    created: bool
    artifact_count: int


class AttributeGeneratorRequest(BaseModel):
    # Not nullable: attributing to `unknown` would be meaningless — the void is what the
    # act fills (ADR-0024).
    generator_version_id: UUID


class PackageArtifactResponse(BaseModel):
    kind: str
    locator: str
    format: str | None


class ContentPackageResponse(BaseModel):
    content_id: UUID
    package_format: str
    # Null when no deployed instance is declared (ADR-0028) — the artifacts stand alone.
    consumable_url: str | None
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
        brief_intake=PackageBriefIntake(HttpFetcher()),
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


@router.post(
    "/register-by-source",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterBySourceResponse,
)
def register_by_source(
    request: RegisterBySourceRequest, admin: AdminAssessor, uow: Uow, response: Response
) -> RegisterBySourceResponse:
    """Register a content version by mechanically discovering a package source (ADR-0027).

    Identity, artifact list and content hash come from the package itself; re-registering
    an unchanged package answers 200 with `created: false` instead of a conflict."""
    if not request.source_locator.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="source_locator must be an http(s) URL — local directories are "
            "registered with the CLI (register-package)",
        )

    register = RegisterContentVersion(
        contents=SqlAlchemyContentRepository(uow.session),
        briefs=SqlAlchemyBriefRepository(uow.session),
        generators=SqlAlchemyGeneratorVersionRepository(uow.session),
        publisher=uow.events,
        uow=uow,
        brief_intake=PackageBriefIntake(HttpFetcher()),
    )
    use_case = RegisterPackageFromSource(PackageDiscovery(HttpPackageRoot), register)
    try:
        registration = use_case(
            RegisterPackageFromSourceCommand(
                package_format=request.package_format,
                source_locator=request.source_locator,
                generator_version_id=request.generator_version_id,
                edit_provenance=request.edit_provenance,
                version=request.version,
            )
        )
    except DuplicateContent as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (
        PackageDiscoveryError,
        InvalidContent,
        InvalidPackage,
        UnknownGeneratorVersion,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    if not registration.created:
        response.status_code = status.HTTP_200_OK
    return RegisterBySourceResponse(
        content=ContentResponse.from_snapshot(_snapshot_or_404(uow, registration.content.id)),
        created=registration.created,
        artifact_count=registration.artifact_count,
    )


@router.get("/formats", response_model=list[str])
def list_package_formats(admin: AdminAssessor) -> list[str]:
    """The package formats discovery supports — what the form offers instead of a
    hardcoded constant (ADR-0027). Declared before `/{content_id}` so the literal path
    is not captured by the parameter."""
    return sorted(DISCOVERIES_BY_FORMAT)


@router.post("/{content_id}/generator", response_model=ContentResponse)
def attribute_generator(
    content_id: UUID, request: AttributeGeneratorRequest, admin: AdminAssessor, uow: Uow
) -> ContentResponse:
    """Record a generator discovered after registration — once, one way (ADR-0024)."""
    use_case = AttributeGenerator(
        contents=SqlAlchemyContentRepository(uow.session),
        generators=SqlAlchemyGeneratorVersionRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        use_case(
            AttributeGeneratorCommand(
                content_id=content_id,
                generator_version_id=request.generator_version_id,
                attributed_by=admin.assessor_id,
            )
        )
    except ContentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GeneratorAlreadyAttributed as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnknownGeneratorVersion as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return ContentResponse.from_snapshot(_snapshot_or_404(uow, content_id))


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
    confirm_distinct_from: str | None = Field(
        default=None,
        description=(
            "Echo of the registered name a refusal named, declaring this generator is a "
            "different one (ADR-0031)."
        ),
    )


class GeneratorResponse(BaseModel):
    generator_id: UUID
    name: str

    @classmethod
    def from_dto(cls, dto: GeneratorDTO) -> "GeneratorResponse":
        return cls(generator_id=dto.generator_id, name=dto.name)


class RegisterGeneratorVersionRequest(BaseModel):
    version: str = Field(examples=["2.4.0"])
    # Free-form identity blob; fields get promoted to typed columns only when consumed.
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneratorVersionResponse(BaseModel):
    generator_version_id: UUID
    generator_id: UUID
    name: str
    version: str
    metadata: dict[str, Any]

    @classmethod
    def from_dto(cls, dto: GeneratorVersionDTO) -> "GeneratorVersionResponse":
        return cls(
            generator_version_id=dto.generator_version_id,
            generator_id=dto.generator_id,
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


@evaluand_router.post(
    "/generators", status_code=status.HTTP_201_CREATED, response_model=GeneratorResponse
)
def register_generator(
    request: RegisterGeneratorRequest, admin: AdminAssessor, uow: Uow
) -> GeneratorResponse:
    """Mint a generator lineage — the rare act (ADR-0031 §3).

    The only gate where a generator name is still typed, hence the only one that guards
    against a near miss. Both refusals are 409: one is the same lineage, the other is a
    question, and the second is answered by echoing the name it named."""
    use_case = RegisterGenerator(
        generators=SqlAlchemyGeneratorRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        generator = use_case(
            RegisterGeneratorCommand(
                name=request.name, confirm_distinct_from=request.confirm_distinct_from
            )
        )
    except (DuplicateGenerator, SimilarGeneratorExists) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidGenerator as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return GeneratorResponse(generator_id=generator.id, name=generator.name)


@evaluand_router.get("/generators", response_model=list[GeneratorResponse])
def list_generators(admin: AdminAssessor, uow: Uow) -> list[GeneratorResponse]:
    dtos = queries.list_generators(SqlAlchemyGeneratorRepository(uow.session))
    return [GeneratorResponse.from_dto(d) for d in dtos]


@evaluand_router.post(
    "/generators/{generator_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=GeneratorVersionResponse,
)
def register_generator_version(
    generator_id: UUID, request: RegisterGeneratorVersionRequest, admin: AdminAssessor, uow: Uow
) -> GeneratorVersionResponse:
    """Register a version under a generator — the routine act. The lineage arrives as a path
    id, so this act has no name to misspell (ADR-0031 §1)."""
    use_case = RegisterGeneratorVersion(
        generators=SqlAlchemyGeneratorRepository(uow.session),
        versions=SqlAlchemyGeneratorVersionRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )
    try:
        version = use_case(
            RegisterGeneratorVersionCommand(
                generator_id=generator_id, version=request.version, metadata=request.metadata
            )
        )
    except UnknownGenerator as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DuplicateGeneratorVersion as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidGeneratorVersion as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    dto = queries.get_generator_version(
        SqlAlchemyGeneratorVersionRepository(uow.session),
        SqlAlchemyGeneratorRepository(uow.session),
        version.id,
    )
    assert dto is not None  # just written in this transaction
    return GeneratorVersionResponse.from_dto(dto)


@evaluand_router.get("/generator-versions", response_model=list[GeneratorVersionResponse])
def list_generator_versions(admin: AdminAssessor, uow: Uow) -> list[GeneratorVersionResponse]:
    dtos = queries.list_generator_versions(
        SqlAlchemyGeneratorVersionRepository(uow.session),
        SqlAlchemyGeneratorRepository(uow.session),
    )
    return [GeneratorVersionResponse.from_dto(d) for d in dtos]


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
