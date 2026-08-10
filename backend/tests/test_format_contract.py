"""The format contract: what EVERY package format must satisfy, parametrized over
`FORMAT_CASES` (`tests/format_cases.py`).

The rules an ADR states per format are asserted here once, for all formats: identity and
hash from the package itself (ADR-0027), no consumable URL from a filesystem root
(ADR-0028), the brief derived or registered absent, never blocking (ADR-0022), supply
meeting demand on shape (ADR-0020). What stays in the per-format test files is each
format's own convention — LearnpackV1's lesson enumeration, activity counting and
calibration corpus live in their existing suites, which this kit complements.

Tests may look across module seams to pin alignments; app code must not.
"""

import shutil
from pathlib import Path

import pytest

from app.modules.content_profiling.application.dtos import ArtifactDTO, PackageDTO
from app.modules.content_profiling.domain.profile import ContentProfile, ExtractionError
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.modules.evaluand_registry.application.ports import PackageDiscoveryError
from app.modules.evaluand_registry.application.register_content_version import (
    DuplicateContent,
    RegisterContentVersion,
)
from app.modules.evaluand_registry.application.register_package_from_source import (
    RegisterPackageFromSource,
    RegisterPackageFromSourceCommand,
)
from app.modules.evaluand_registry.infrastructure.brief_intake import (
    BRIEF_INTAKES_BY_FORMAT,
    PackageBriefIntake,
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
from app.shared.domain.ids import new_id
from app.shared.domain.value_domain import check_value, validate_spec
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher
from tests.conftest import declared_value_domains
from tests.format_cases import FORMAT_CASES, FormatCase

# ------------------------------------------------------------------ the case, per format


@pytest.fixture(params=sorted(FORMAT_CASES), ids=str)
def case(request) -> FormatCase:
    return FORMAT_CASES[request.param]


def discover(case: FormatCase, fixture_dir: Path | None = None, locator_base: str | None = None):
    root = FilesystemPackageRoot(fixture_dir or case.fixture_dir, locator_base=locator_base)
    return DISCOVERIES_BY_FORMAT[case.package_format].discover(root)


def mutated_copy(case: FormatCase, tmp_path: Path) -> Path:
    """A copy of the fixture with one discovered artifact's bytes changed — the generic
    way to drift a package without knowing the format's file layout: with no locator
    base, every locator IS a root-relative path."""
    copy = tmp_path / case.fixture_dir.name
    shutil.copytree(case.fixture_dir, copy)
    target = copy / discover(case).artifacts[-1].locator
    target.write_bytes(target.read_bytes() + b"\ndrifted")
    return copy


# ------------------------------------------------------------------ registries and cases


def test_every_registered_format_has_a_case():
    """The lock: registering a format in any registry without adding its `FormatCase`
    fails here — the kit cannot be skipped by omission. And a case without a registered
    format is a leftover, equally refused."""
    registered = set(DISCOVERIES_BY_FORMAT) | set(ADAPTERS_BY_FORMAT) | set(BRIEF_INTAKES_BY_FORMAT)
    assert registered == set(FORMAT_CASES)
    # Discovery is the one non-optional adapter (runbook step 2): a format that cannot
    # be registered from a source is not a format this system supports.
    assert registered <= set(DISCOVERIES_BY_FORMAT)


def test_the_case_agrees_with_the_registries(case):
    # `expected_capabilities` is None exactly while no extraction adapter exists.
    assert (case.expected_capabilities is not None) == (case.package_format in ADAPTERS_BY_FORMAT)
    if case.expects_brief:
        assert case.package_format in BRIEF_INTAKES_BY_FORMAT


def test_an_unknown_format_is_refused():
    any_fixture = next(iter(FORMAT_CASES.values())).fixture_dir
    with pytest.raises(PackageDiscoveryError):
        PackageDiscovery().discover("NoSuchFormat", str(any_fixture))


def test_the_declared_value_domains_are_well_formed():
    """The demand-side namespace every adapter declares against (ADR-0020)."""
    assert [p for d in declared_value_domains().values() for p in validate_spec(d)] == []


# ------------------------------------------------------------------ discovery (step 2)


def test_discovery_reads_identity_from_the_package(case):
    discovered = discover(case)
    assert discovered.package_format == case.package_format
    assert discovered.external_id == case.expected_external_id
    assert {a.kind for a in discovered.artifacts} == case.expected_artifact_kinds
    assert discovered.content_hash


def test_the_hash_is_deterministic_and_root_independent(case):
    """Keyed by root-relative path (ADR-0027): the same package hashes identically from
    any serving root — what makes dedupe work across fixtures, the dev mount and
    production."""
    assert (
        discover(case).content_hash
        == discover(case, locator_base="served/from/elsewhere").content_hash
    )


def test_changed_bytes_change_the_hash(case, tmp_path):
    drifted = discover(case, fixture_dir=mutated_copy(case, tmp_path))
    assert drifted.content_hash != discover(case).content_hash


def test_a_filesystem_discovery_yields_no_consumable_url(case):
    """ADR-0028: serving a package's bytes is transport, not deployment — even when the
    locators are honest mount URLs."""
    discovered = discover(case, locator_base="http://localhost:8000/packages/g@1/c")
    assert discovered.consumable_url is None


# ------------------------------------------------------------------ brief intake (step 4)


class _FailingFetcher:
    def fetch(self, locator: str) -> bytes:
        raise FetchError(f"unreachable: {locator}")


class _CorruptFetcher:
    def fetch(self, locator: str) -> bytes:
        return b"\x00 not parseable by any format"


def _artifact_rows(case: FormatCase) -> list[dict]:
    return [{"kind": a.kind, "locator": a.locator} for a in discover(case).artifacts]


def test_the_brief_derives_or_registers_absent(case):
    """ADR-0022: the fixture's commission derives a brief exactly when the case says the
    format carries one; a format without an intake misses softly."""
    intake = PackageBriefIntake(FilesystemFetcher(case.fixture_dir))
    derived = intake.derive(case.package_format, _artifact_rows(case))
    assert (derived is not None) == case.expects_brief


def test_the_intake_never_blocks(case):
    """ADR-0022: any miss — fetch failure, corrupt payload — derives None, so the
    registration proceeds with the brief absent. An intake that lets an exception
    escape here breaks the contract."""
    if case.package_format not in BRIEF_INTAKES_BY_FORMAT:
        pytest.skip("no brief intake for this format — soft absence is already the behavior")
    rows = _artifact_rows(case)
    assert PackageBriefIntake(_FailingFetcher()).derive(case.package_format, rows) is None
    assert PackageBriefIntake(_CorruptFetcher()).derive(case.package_format, rows) is None


# ------------------------------------------------------------------ extraction (step 3)


@pytest.fixture
def extraction(case):
    """The seam wired the way production wires it: the artifacts discovery minted are
    exactly what the extraction adapter reads."""
    if case.expected_capabilities is None:
        pytest.skip("no extraction adapter registered yet (runbook step 3 pending)")
    package = PackageDTO(
        content_id=new_id(),
        package_format=case.package_format,
        artifacts=tuple(
            ArtifactDTO(kind=a.kind, locator=a.locator, format=a.format)
            for a in discover(case).artifacts
        ),
    )
    adapter = ADAPTERS_BY_FORMAT[case.package_format]
    return adapter, package, FilesystemPackageFetcher(case.fixture_dir)


def test_capabilities_name_declared_requirements(case):
    if case.expected_capabilities is None:
        pytest.skip("no extraction adapter registered yet (runbook step 3 pending)")
    adapter = ADAPTERS_BY_FORMAT[case.package_format]
    assert adapter.package_format == case.package_format
    assert adapter.capabilities == case.expected_capabilities
    # Capabilities are declared against the namespace the instrument mints (ADR-0014):
    # an id with no declaration behind it is a capability nothing can consume.
    assert adapter.capabilities <= set(declared_value_domains())


def test_discovery_feeds_extraction(extraction, case):
    """One entry per declared capability — and nothing else (ADR-0009)."""
    adapter, package, fetcher = extraction
    entries, _ = adapter.extract(package, fetcher)
    assert {e.data_requirement_id for e in entries} == case.expected_capabilities


def test_extraction_is_deterministic(extraction):
    adapter, package, fetcher = extraction
    assert adapter.extract(package, fetcher) == adapter.extract(package, fetcher)


def test_every_extracted_value_matches_its_declared_value_domain(extraction):
    """Supply meets demand on SHAPE (ADR-0020), over the real fixture."""
    adapter, package, fetcher = extraction
    domains = declared_value_domains()
    entries, _ = adapter.extract(package, fetcher)
    problems = [
        problem
        for e in entries
        if e.provenance != "absent"
        for problem in check_value(e.value, domains[e.data_requirement_id], e.data_requirement_id)
    ]
    assert problems == []


def test_extraction_satisfies_the_profile_aggregate(extraction, case):
    """The adapter's output builds a valid ok profile — the two halves fit."""
    adapter, package, fetcher = extraction
    entries, extras = adapter.extract(package, fetcher)
    profile = ContentProfile.ok(
        id=new_id(),
        content_id=package.content_id,
        package_format=case.package_format,
        adapter_version=adapter.adapter_version,
        capabilities=adapter.capabilities,
        value_domains=declared_value_domains(),
        entries=entries,
        extras=extras,
    )
    assert profile.status == "ok"


def test_an_unreadable_package_fails_extraction_whole(extraction):
    """Never a half-profile: a package whose artifacts cannot be fetched raises
    `ExtractionError` — it does not silently narrow to what was reachable."""
    adapter, package, _ = extraction

    class UnreachableFetcher:
        def fetch(self, locator: str) -> bytes:
            raise ExtractionError(f"unreachable: {locator}")

    with pytest.raises(ExtractionError):
        adapter.extract(package, UnreachableFetcher())


# ------------------------------------------------------------------ registration (DB)


def _register_from(case: FormatCase, source_dir: Path):
    """The one canonical path (ADR-0027): discovery feeds `RegisterContentVersion`,
    with the intake reading the discovered artifacts."""
    from app.platform.db import SessionLocal
    from app.platform.uow import UnitOfWork

    with SessionLocal() as session:
        uow = UnitOfWork(session)
        register = RegisterContentVersion(
            contents=SqlAlchemyContentRepository(session),
            briefs=SqlAlchemyBriefRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
            brief_intake=PackageBriefIntake(FilesystemFetcher(source_dir)),
        )
        return RegisterPackageFromSource(PackageDiscovery(), register)(
            RegisterPackageFromSourceCommand(
                package_format=case.package_format,
                source_locator=str(source_dir),
                generator_version_id=None,
            )
        )


def _track(cleanup, registration):
    cleanup["contents"].append(registration.content.id)
    if registration.content.brief_id and registration.content.brief_id not in cleanup["briefs"]:
        cleanup["briefs"].append(registration.content.brief_id)
    return registration


def test_registration_by_discovery_round_trips(case, cleanup, session):
    first = _track(cleanup, _register_from(case, case.fixture_dir))
    content = first.content

    assert first.created
    assert content.external_id == case.expected_external_id  # identity from the package
    assert content.consumable_url is None  # filesystem source: no deployment (ADR-0028)
    assert content.content_hash
    assert first.artifact_count == len(discover(case).artifacts)
    assert (content.brief_id is not None) == case.expects_brief  # ADR-0022

    second = _track(cleanup, _register_from(case, case.fixture_dir))
    assert not second.created  # unchanged content re-imports as a reported no-op
    assert second.content.id == content.id


def test_changed_content_under_the_same_version_is_refused(case, cleanup, session, tmp_path):
    _track(cleanup, _register_from(case, case.fixture_dir))

    with pytest.raises(DuplicateContent, match="declare a new version"):
        _register_from(case, mutated_copy(case, tmp_path))
