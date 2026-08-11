"""Dev-only intake from the declared local source roots (ADR-0035).

Browse a root, preview what registering each folder inside it would do, then register the
ones worth registering. The registration itself is `RegisterPackageFromSource`, untouched:
this is a new caller, not a second intake path (ADR-0027 §3), which is why parity with
`app.cli register-package` is a property rather than something to maintain.

Two things about this module are load-bearing and easy to undo by accident:

**Every handler is `def`, never `async def`.** Discovery, the brief intake and the mount
probe all issue blocking HTTP calls back into *this* process — the locators point at the
mounts this same app serves. A `def` handler runs in the threadpool and the event loop stays
free to answer them; an `async def` handler would block the loop waiting on a response only
that loop can produce, and deadlock against itself.

**The local-mode gate is on the router**, so it is resolved before `AdminAssessor`: outside
local mode these paths answer 404 and not 401 (ADR-0035 §3).
"""

from collections import defaultdict
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.modules.evaluand_registry.application import queries
from app.modules.evaluand_registry.application.ports import PackageDiscoveryError
from app.modules.evaluand_registry.application.register_content_version import (
    DuplicateContent,
    RegisterContentVersion,
    UnknownGeneratorVersion,
)
from app.modules.evaluand_registry.application.register_package_from_source import (
    RegisterPackageFromSource,
    RegisterPackageFromSourceCommand,
)
from app.modules.evaluand_registry.domain.content import (
    DEFAULT_VERSION,
    EducationalContent,
    InvalidContent,
)
from app.modules.evaluand_registry.domain.package import InvalidPackage
from app.modules.evaluand_registry.infrastructure import local_sources
from app.modules.evaluand_registry.infrastructure.brief_intake import PackageBriefIntake
from app.modules.evaluand_registry.infrastructure.local_sources import (
    LocalSourceError,
    SourceRoot,
)
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    DISCOVERIES_BY_FORMAT,
    FilesystemPackageRoot,
    PackageDiscovery,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.modules.evaluand_registry.infrastructure.router import ContentResponse
from app.platform.security import AdminAssessor, require_local_mode
from app.platform.uow import UnitOfWork, get_uow
from app.shared.infrastructure.fetchers import FetchError, HttpFetcher

router = APIRouter(
    prefix="/dev/local-courses",
    tags=["dev"],
    dependencies=[Depends(require_local_mode)],
)

Uow = Annotated[UnitOfWork, Depends(get_uow)]

# What registering a folder would do, derived from the same rules RegisterContentVersion
# applies (ADR-0035 §4). `new_version` is the one that is easy to miss: the course is known,
# the bytes are new, and the declared version is free — so it registers, and calling it
# `new` would tell an operator scanning a regenerated population something false.
VERDICT_NEW = "new"
VERDICT_NEW_VERSION = "new_version"
VERDICT_UNCHANGED = "unchanged"
VERDICT_CONFLICT = "conflict"
VERDICT_UNREADABLE = "unreadable"


class SourceRootResponse(BaseModel):
    key: str
    path: str
    url_base: str
    #: Read live. It does not say the tree is served — only the mount probe knows that.
    exists: bool
    builtin: bool


class FolderEntry(BaseModel):
    name: str
    path: str
    #: How many folders it holds, so "you are one level too high" is visible before scanning.
    child_dir_count: int


class BrowseResponse(BaseModel):
    root: str
    path: str
    parent: str | None
    entries: list[FolderEntry]


class ExistingContent(BaseModel):
    content_id: UUID
    version: str
    generator_version_id: UUID | None
    #: False for rows registered by hand before ADR-0027 — they never dedupe by content.
    has_hash: bool


class ScanCandidate(BaseModel):
    name: str
    path: str
    verdict: str
    external_id: str | None = None
    title: str | None = None
    artifact_count: int | None = None
    content_hash: str | None = None
    #: Why discovery refused, for `unreadable` only.
    error: str | None = None
    #: The registered row this verdict is about. For `new_version`, the most recent one.
    existing: ExistingContent | None = None
    #: The existing row declares no generator, so the attribution act applies (ADR-0024).
    can_attribute_generator: bool = False


class ScanRequest(BaseModel):
    root: str
    path: str = ""
    package_format: str = Field(examples=["LearnpackV2"])
    version: str = DEFAULT_VERSION


class ScanResponse(BaseModel):
    #: Whether the locators these folders would register are actually fetchable.
    mount_ok: bool
    mount_detail: str | None
    candidates: list[ScanCandidate]


class RegisterLocalRequest(BaseModel):
    root: str
    #: The package directory itself, as `scan` returned it.
    path: str
    package_format: str = Field(examples=["LearnpackV2"])
    version: str = DEFAULT_VERSION
    # Required, and null is a legal value (ADR-0024): null declares `unknown`.
    generator_version_id: UUID | None = Field(...)
    edit_provenance: str = "unknown"


class RegisterLocalResponse(BaseModel):
    content: ContentResponse
    created: bool
    artifact_count: int
    #: True when the registered content still declares no generator — including the case
    #: where this call was a no-op and the generator it declared was discarded (ADR-0035 §9).
    can_attribute_generator: bool


def _root_or_404(key: str) -> SourceRoot:
    root = local_sources.root_for(key)
    if root is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"'{key}' is not a local source root"
        )
    if not root.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"the '{key}' source root does not exist at {root.path.as_posix()}",
        )
    return root


def _directory_or_422(root: SourceRoot, path: str) -> Path:
    try:
        return local_sources.resolve(root, path)
    except LocalSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


def _known_format_or_422(package_format: str) -> None:
    """Checked before anything touches the disk: otherwise every candidate in the scan
    comes back with the same useless error."""
    if package_format not in DISCOVERIES_BY_FORMAT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"no discovery is registered for format '{package_format}'",
        )


def _probe_mount(package: FilesystemPackageRoot, directory: Path) -> str | None:
    """One real fetch through the served URL, before any of these locators is written.

    The API serving the mount is not the same statement as the mount being reachable at the
    URL the locators carry: the base URL can name another host or port, a root created after
    boot was never mounted, and a symlink this process reads is one StaticFiles refuses to
    follow. Every one of those registers rows whose locators 404 forever (ADR-0035 §6).

    The probe is a file the package actually has, picked off disk — what is checked is that
    the tree is served, which is true of every format. Probing a named manifest would make
    the check format-specific.
    """
    probe = next((path for path in sorted(directory.rglob("*")) if path.is_file()), None)
    if probe is None:
        return None  # nothing to serve; discovery refuses it with a better message
    locator = package.locator_for(probe.relative_to(directory).as_posix())
    try:
        HttpFetcher().fetch(locator)
    except FetchError as exc:
        return (
            f"the app does not serve this tree at {locator} ({exc}). Registered locators "
            "point there, so without it the brief intake and profiling would fail later."
        )
    return None


def _registered_by_external_id(
    uow: UnitOfWork, package_format: str
) -> dict[str, list[EducationalContent]]:
    """Everything already registered in this format, in one read. The verdicts fall out of
    it in memory — a dev-only preview does not earn a new repository method."""
    registered: dict[str, list[EducationalContent]] = defaultdict(list)
    for content in SqlAlchemyContentRepository(uow.session).list_filtered(
        package_format=package_format
    ):
        registered[content.external_id].append(content)
    return registered


def _verdict(
    content_hash: str, declared_version: str, existing: list[EducationalContent]
) -> tuple[str, EducationalContent | None]:
    """The five outcomes of `RegisterContentVersion`, in the order it decides them: the hash
    match wins over everything (across all versions), then the declared version being taken,
    then the course being known at some other version."""
    same_content = next((c for c in existing if c.content_hash == content_hash), None)
    if same_content is not None:
        return VERDICT_UNCHANGED, same_content
    occupied = next((c for c in existing if c.version == declared_version), None)
    if occupied is not None:
        return VERDICT_CONFLICT, occupied
    if existing:
        # Ordered by registration, so the last one is what the operator saw most recently.
        return VERDICT_NEW_VERSION, existing[-1]
    return VERDICT_NEW, None


def _existing_response(content: EducationalContent | None) -> ExistingContent | None:
    if content is None:
        return None
    return ExistingContent(
        content_id=content.id,
        version=content.version,
        generator_version_id=content.generator_version_id,
        has_hash=content.content_hash is not None,
    )


@router.get("/roots", response_model=list[SourceRootResponse])
def list_source_roots(admin: AdminAssessor) -> list[SourceRootResponse]:
    """The trees this process may register from — the built-in `courses/` first."""
    return [
        SourceRootResponse(
            key=root.key,
            path=root.path.as_posix(),
            url_base=root.url_base,
            exists=root.exists,
            builtin=root.builtin,
        )
        for root in local_sources.configured_roots()
    ]


@router.get("/browse", response_model=BrowseResponse)
def browse_source_root(admin: AdminAssessor, root: str, path: str = "") -> BrowseResponse:
    """The folders directly inside `path`. Navigation only — nothing here reads a package."""
    source_root = _root_or_404(root)
    directory = _directory_or_422(source_root, path)
    relative = local_sources.relative_to(source_root, directory)

    entries = []
    for child in sorted(item for item in directory.iterdir() if item.is_dir()):
        try:
            child_dirs = sum(1 for item in child.iterdir() if item.is_dir())
        except OSError:
            # Unreadable is not an error worth failing the listing over; it scans to nothing.
            child_dirs = 0
        entries.append(
            FolderEntry(
                name=child.name,
                path=f"{relative}/{child.name}" if relative else child.name,
                child_dir_count=child_dirs,
            )
        )

    return BrowseResponse(
        root=source_root.key,
        path=relative,
        parent=None if not relative else relative.rpartition("/")[0],
        entries=entries,
    )


@router.post("/scan", response_model=ScanResponse)
def scan_source_folder(request: ScanRequest, admin: AdminAssessor, uow: Uow) -> ScanResponse:
    """What registering each folder inside `path` would do — before anything is written.

    A POST although it writes nothing: it fetches and hashes every artifact of every folder,
    which can take minutes and must never be cached, prefetched or retried by a proxy.

    The answer is a preview and only a preview: `register` re-discovers everything, so a
    stale scan can be wrong about a label and never about what gets written.
    """
    source_root = _root_or_404(request.root)
    _known_format_or_422(request.package_format)
    directory = _directory_or_422(source_root, request.path)
    relative = local_sources.relative_to(source_root, directory)

    registered = _registered_by_external_id(uow, request.package_format)
    candidates: list[ScanCandidate] = []
    mount_detail: str | None = None
    probed = False

    for child in sorted(item for item in directory.iterdir() if item.is_dir()):
        child_relative = f"{relative}/{child.name}" if relative else child.name
        package = local_sources.package_root(source_root, child_relative)
        discovery = PackageDiscovery(local_sources.fixed_root(package))
        try:
            discovered = discovery.discover(request.package_format, child_relative)
        except PackageDiscoveryError as exc:
            candidates.append(
                ScanCandidate(
                    name=child.name,
                    path=child_relative,
                    verdict=VERDICT_UNREADABLE,
                    error=str(exc),
                )
            )
            continue

        # Once per scan, on the first folder that turned out to be a package: what is being
        # checked is the tree, and every readable folder in it is served the same way.
        if not probed:
            mount_detail = _probe_mount(package, child)
            probed = True

        verdict, existing = _verdict(
            discovered.content_hash, request.version, registered[discovered.external_id]
        )
        candidates.append(
            ScanCandidate(
                name=child.name,
                path=child_relative,
                verdict=verdict,
                external_id=discovered.external_id,
                title=discovered.title,
                artifact_count=len(discovered.artifacts),
                content_hash=discovered.content_hash,
                existing=_existing_response(existing),
                can_attribute_generator=existing is not None
                and existing.generator_version_id is None,
            )
        )

    return ScanResponse(
        mount_ok=mount_detail is None, mount_detail=mount_detail, candidates=candidates
    )


@router.post("/register", response_model=RegisterLocalResponse, status_code=status.HTTP_201_CREATED)
def register_local_package(
    request: RegisterLocalRequest, admin: AdminAssessor, uow: Uow, response: Response
) -> RegisterLocalResponse:
    """Register one folder. A selection is a loop in the caller, deliberately (ADR-0035 §5):
    every created course auto-profiles inside its own request (ADR-0029), so a whole-tree
    call would be a multi-minute write with no progress and no bounded failure.

    Re-registering an unchanged package answers 200 with `created: false` instead of a
    conflict — and, if that content declares no generator, the one this call declared is
    discarded rather than applied. `can_attribute_generator` says so; filling it is the
    explicit act of ADR-0024, never a side effect of a re-scan.
    """
    source_root = _root_or_404(request.root)
    _known_format_or_422(request.package_format)
    directory = _directory_or_422(source_root, request.path)
    package = local_sources.package_root(source_root, request.path)

    # Binding, not advisory (ADR-0035 §6): the locators about to be written are permanent.
    detail = _probe_mount(package, directory)
    if detail is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)

    register = RegisterContentVersion(
        contents=SqlAlchemyContentRepository(uow.session),
        briefs=SqlAlchemyBriefRepository(uow.session),
        generators=SqlAlchemyGeneratorVersionRepository(uow.session),
        publisher=uow.events,
        uow=uow,
        # Locators are mount URLs, so the intake fetches them over http — as on every other
        # registration path.
        brief_intake=PackageBriefIntake(HttpFetcher()),
    )
    discovery = PackageDiscovery(local_sources.fixed_root(package))
    use_case = RegisterPackageFromSource(discovery, register)
    try:
        registration = use_case(
            RegisterPackageFromSourceCommand(
                package_format=request.package_format,
                source_locator=request.path,
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

    snapshot = queries.get_content_snapshot(
        SqlAlchemyContentRepository(uow.session), registration.content.id
    )
    assert snapshot is not None  # it was just written, or it was already there
    return RegisterLocalResponse(
        content=ContentResponse.from_snapshot(snapshot),
        created=registration.created,
        artifact_count=registration.artifact_count,
        can_attribute_generator=snapshot.generator_version_id is None,
    )
