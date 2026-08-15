"""Admin endpoints of Content Profiling — the designer's workbench feed (ADR-0012), and
the two acts it performs.

The acts were CLI-only while profiling was something the team drove by hand. They are not
page buttons because the console got prettier: accepting an extraction is what lets anyone
discard "broken extraction" as an explanation, and it is taken after reading the profiles
this same screen renders — so the act belongs beside the evidence, not in another tool.

Both are deliberate and recorded with their author, like publishing an instrument and
ratifying an assessor, and both take that author from the request rather than from a flag.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.modules.content_profiling.application.accept_extraction import (
    AcceptExtraction,
    AcceptExtractionCommand,
)
from app.modules.content_profiling.application.dtos import (
    CapabilitiesSnapshot,
    ContentProfileSnapshot,
)
from app.modules.content_profiling.application.profile_content import (
    ContentNotFound,
    NoAdapterForFormat,
    ProfileAlreadyExists,
    ProfileContent,
    ProfileContentCommand,
)
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.fetchers import HttpPackageFetcher
from app.modules.content_profiling.infrastructure.gateways import (
    DesignNamespaceGateway,
    RegistryContentGateway,
)
from app.modules.content_profiling.infrastructure.repository import (
    SqlAlchemyAcceptanceRepository,
    SqlAlchemyProfileRepository,
)
from app.modules.content_profiling.public import ContentProfilingQueries
from app.modules.evaluand_registry.public import EvaluandRegistryQueries
from app.platform.security import AdminAssessor
from app.platform.uow import UnitOfWork, get_uow

router = APIRouter(prefix="/admin", tags=["content-profiling"])

Uow = Annotated[UnitOfWork, Depends(get_uow)]

#: The automatic path fetches over http and only over http (ADR-0029), and so does this one.
_HTTP_SCHEMES = ("http://", "https://")


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


class AcceptExtractionResponse(BaseModel):
    package_format: str
    #: Which version was accepted — resolved from the running adapter, never sent by a client.
    adapter_version: str
    #: False when this pair was already accepted. The act is idempotent, and saying it did
    #: not happen again is not the same as saying nothing is accepted.
    newly_accepted: bool


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


@router.post("/profiling/{package_format}/accept", response_model=AcceptExtractionResponse)
def accept_extraction(
    package_format: str, admin: AdminAssessor, uow: Uow
) -> AcceptExtractionResponse:
    """Qualify the current adapter version of a format (ADR-0012).

    The version is not in the path: what is accepted is the adapter this deployment runs,
    resolved here exactly as `accept-extraction --package-format` resolves it. Accepting a
    version nobody is running would record a judgement about code that is not there.
    """
    adapter = ADAPTERS_BY_FORMAT.get(package_format)
    if adapter is None:
        known = ", ".join(sorted(ADAPTERS_BY_FORMAT)) or "none"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no extraction adapter for '{package_format}' (registered: {known})",
        )

    newly_accepted = AcceptExtraction(
        acceptances=SqlAlchemyAcceptanceRepository(uow.session),
        publisher=uow.events,
        uow=uow,
    )(
        AcceptExtractionCommand(
            package_format=package_format,
            adapter_version=adapter.adapter_version,
            accepted_by=admin.assessor_id,
        )
    )
    return AcceptExtractionResponse(
        package_format=package_format,
        adapter_version=adapter.adapter_version,
        newly_accepted=newly_accepted,
    )


@router.post("/contents/{content_id}/profile", response_model=ProfileResponse)
def profile_content(content_id: UUID, admin: AdminAssessor, uow: Uow) -> ProfileResponse:
    """Read one package now — the manual path, which is how the samples that earn an
    acceptance are produced, and the only way a `failed` profile is ever retried.

    A batch is a loop in the caller (ADR-0035 §5): each package is fetched and parsed, so
    one request per content is what keeps a slow one visible and a failure bounded.
    """
    package = RegistryContentGateway(uow.session).get_package(content_id)
    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"content {content_id} is not registered"
        )
    adapter = ADAPTERS_BY_FORMAT.get(package.package_format)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"no extraction adapter for package format '{package.package_format}'",
        )

    # Asked before the transport, so every combination answers the truth. A package that is
    # already read AND rooted on a filesystem is not a transport problem: there is nothing
    # to do about it on any path, and pointing at `--base-dir` would send someone to a
    # command that skips it too. The rule itself still lives in the use case, which refuses
    # the same thing again if a concurrent write lands between here and there.
    if (
        SqlAlchemyProfileRepository(uow.session).get_status(content_id, adapter.adapter_version)
        == "ok"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"content {content_id} already has an ok profile for adapter version "
                f"{adapter.adapter_version} — profiles are immutable; a different extraction "
                "is a new adapter version"
            ),
        )

    # The same refusal the policy makes, and for the same reason: letting an unreachable
    # package through would commit a `failed` profile, and those coordinates are then
    # refused in EITHER state — so the row would be stuck on a package that reads perfectly
    # from a filesystem base dir. `reprofile --base-dir` is that path; this one is http.
    if not all(artifact.locator.startswith(_HTTP_SCHEMES) for artifact in package.artifacts):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"content {content_id} is rooted on a filesystem, and this path fetches over "
                "http only (ADR-0029) — read it with `app.cli reprofile --base-dir <dir>`"
            ),
        )

    use_case = ProfileContent(
        profiles=SqlAlchemyProfileRepository(uow.session),
        contents=RegistryContentGateway(uow.session),
        namespace=DesignNamespaceGateway(uow.session),
        adapters=ADAPTERS_BY_FORMAT,
        fetcher=HttpPackageFetcher(),
        publisher=uow.events,
        uow=uow,
    )
    try:
        profile = use_case(ProfileContentCommand(content_id=content_id))
    except ContentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NoAdapterForFormat as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except ProfileAlreadyExists as exc:
        # An `ok` profile is final. Not a retry that failed — a request that has no meaning.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    snapshot = ContentProfilingQueries(uow.session).get_profile(content_id, profile.adapter_version)
    if snapshot is None:  # pragma: no cover — written in the transaction just committed
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"content {content_id} was profiled but the profile cannot be read back",
        )
    return ProfileResponse.from_snapshot(snapshot, _content_identities(uow).get(content_id))
