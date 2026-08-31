"""Registering from a source: discovery feeds the one canonical path (ADR-0027).

`RegisterContentVersion` stays the only writer of contents; what these tests pin is the
composition — descriptor and artifacts from discovery, brief from the discovered syllabus,
and the content-hash identity: unchanged → no-op, changed under the same declared version →
refused.
"""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import text

from app.modules.evaluand_registry.application.register_content_version import (
    DuplicateContent,
    RegisterContentVersion,
)
from app.modules.evaluand_registry.application.register_package_from_source import (
    DeclaredGeneratorConflict,
    RegisterPackageFromSource,
    RegisterPackageFromSourceCommand,
)
from app.modules.evaluand_registry.infrastructure.brief_intake import PackageBriefIntake
from app.modules.evaluand_registry.infrastructure.package_discovery import (
    FilesystemPackageRoot,
    PackageDiscovery,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.infrastructure.fetchers import FilesystemFetcher

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"

CONSUMABLE = "https://bare-course.learn-pack.com/"


def fixtures_root(locator: str) -> FilesystemPackageRoot:
    return FilesystemPackageRoot(FIXTURES / locator, locator_base=locator)


def use_case(session, root_factory=fixtures_root) -> RegisterPackageFromSource:
    uow = UnitOfWork(session)
    register = RegisterContentVersion(
        contents=SqlAlchemyContentRepository(session),
        briefs=SqlAlchemyBriefRepository(session),
        generators=SqlAlchemyGeneratorVersionRepository(session),
        publisher=uow.events,
        uow=uow,
        brief_intake=PackageBriefIntake(FilesystemFetcher(FIXTURES)),
    )
    return RegisterPackageFromSource(
        PackageDiscovery(root_factory),
        register,
        SqlAlchemyGeneratorRepository(session),
        SqlAlchemyGeneratorVersionRepository(session),
    )


def register_bare(cleanup, session=None, **overrides):
    command = RegisterPackageFromSourceCommand(
        package_format="LearnpackV1",
        source_locator="bare-course",
        generator_version_id=None,
        consumable_url=CONSUMABLE,
        **overrides,
    )
    with SessionLocal() as s:
        registration = use_case(s)(command)
    cleanup["contents"].append(registration.content.id)
    return registration


def test_registers_the_discovered_package(cleanup, session):
    registration = register_bare(cleanup)
    content = registration.content

    assert registration.created
    assert content.external_id == "bare-course"  # identity comes from the package, not a form
    # The name is the package's, kept beside the identity rather than dropped (ADR-0059).
    assert content.title == "Bare Course"
    assert content.consumable_url == CONSUMABLE
    assert content.content_hash
    # learn.json, package-manifest, two lesson bodies, one exercise file — no syllabus.
    assert registration.artifact_count == 5
    persisted = session.execute(
        text("SELECT count(*) FROM content_package_artifacts WHERE content_id = :id"),
        {"id": content.id},
    ).scalar()
    assert persisted == 5


def test_the_declared_title_is_persisted(cleanup, session):
    """ADR-0059: what discovery read off `learn.json` survives the registration, and is
    read back from the row rather than from the object the use case returned."""
    content = register_bare(cleanup).content

    stored = session.execute(
        text("SELECT title FROM contents WHERE id = :id"), {"id": content.id}
    ).scalar()
    assert stored == "Bare Course"


def test_reimporting_unchanged_content_is_a_noop(cleanup, session):
    first = register_bare(cleanup)
    second = register_bare(cleanup)

    assert not second.created
    assert second.content.id == first.content.id


def test_identical_content_under_a_new_declared_version_is_a_noop(cleanup, session):
    first = register_bare(cleanup)
    second = register_bare(cleanup, version="2")

    assert not second.created
    assert second.content.id == first.content.id
    versions = session.execute(
        text("SELECT count(*) FROM contents WHERE external_id = 'bare-course'")
    ).scalar()
    assert versions == 1


def test_changed_content_under_the_same_version_is_refused(cleanup, session, tmp_path):
    register_bare(cleanup)

    shutil.copytree(FIXTURES / "bare-course", tmp_path / "bare-course")
    readme = tmp_path / "bare-course" / "exercises" / "00-frontmatter-only" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\ndrifted", encoding="utf-8")

    with SessionLocal() as s:
        drifted = use_case(s, lambda loc: FilesystemPackageRoot(Path(loc)))
        with pytest.raises(DuplicateContent, match="declare a new version"):
            drifted(
                RegisterPackageFromSourceCommand(
                    package_format="LearnpackV1",
                    source_locator=str(tmp_path / "bare-course"),
                    generator_version_id=None,
                    consumable_url=CONSUMABLE,
                )
            )


def test_a_filesystem_source_registers_without_a_consumable_url(cleanup, session):
    """ADR-0028: a filesystem root declares no deployment, and that no longer refuses the
    registration — the package is a complete evaluand for the automated path."""
    with SessionLocal() as s:
        registration = use_case(s)(
            RegisterPackageFromSourceCommand(
                package_format="LearnpackV1",
                source_locator="bare-course",
                generator_version_id=None,  # and no declaration either
            )
        )
    content = registration.content
    cleanup["contents"].append(content.id)

    assert registration.created
    assert content.consumable_url is None
    assert registration.artifact_count == 5  # the package is whole; only the URL is absent
    stored = session.execute(
        text("SELECT consumable_url FROM contents WHERE id = :id"), {"id": content.id}
    ).scalar()
    assert stored is None


def test_the_brief_derives_from_the_discovered_syllabus(cleanup, session):
    with SessionLocal() as s:
        registration = use_case(s)(
            RegisterPackageFromSourceCommand(
                package_format="LearnpackV1",
                source_locator="introduction-to-generative-ai",
                generator_version_id=None,
                consumable_url="https://introduction-to-generative-ai.learn-pack.com/",
            )
        )
    content = registration.content
    cleanup["contents"].append(content.id)
    if content.brief_id:
        cleanup["briefs"].append(content.brief_id)

    assert content.brief_id is not None  # ADR-0022, fed by the discovered syllabus artifact


def test_the_generator_declaration_has_no_default():
    """ADR-0024 carries through: the command cannot be built without a declaration."""
    with pytest.raises(TypeError):
        RegisterPackageFromSourceCommand(
            package_format="LearnpackV1",
            source_locator="bare-course",
        )  # type: ignore[call-arg]


# --- Cross-checking a declared generator against the package's own claim (ADR-0027 §5) ----
#
# LearnpackV1 fixtures never declare a generator (ADR-0017 §3: V1 has nothing to read), so
# these tests overlay a declared name/version on top of a real discovery — the same shape
# LearnpackV2 populates from `traces/run_metadata.json`, without needing a V2 fixture tree.


class _DeclaringDiscovery:
    def __init__(self, inner, declared_generator_name, declared_generator_version):
        self._inner = inner
        self._name = declared_generator_name
        self._version = declared_generator_version

    def discover(self, package_format, source_locator):
        discovered = self._inner.discover(package_format, source_locator)
        return replace(
            discovered,
            declared_generator_name=self._name,
            declared_generator_version=self._version,
        )


def use_case_declaring(session, declared_generator_name, declared_generator_version):
    uow = UnitOfWork(session)
    register = RegisterContentVersion(
        contents=SqlAlchemyContentRepository(session),
        briefs=SqlAlchemyBriefRepository(session),
        generators=SqlAlchemyGeneratorVersionRepository(session),
        publisher=uow.events,
        uow=uow,
        brief_intake=PackageBriefIntake(FilesystemFetcher(FIXTURES)),
    )
    discovery = _DeclaringDiscovery(
        PackageDiscovery(fixtures_root), declared_generator_name, declared_generator_version
    )
    return RegisterPackageFromSource(
        discovery,
        register,
        SqlAlchemyGeneratorRepository(session),
        SqlAlchemyGeneratorVersionRepository(session),
    )


def test_a_declared_generator_matching_the_selection_registers_normally(
    cleanup, register_generator_version, unique
):
    version_id = register_generator_version(f"Declaring Generator {unique}", "2.0.0")

    with SessionLocal() as s:
        registration = use_case_declaring(s, f"Declaring Generator {unique}", "2.0.0")(
            RegisterPackageFromSourceCommand(
                package_format="LearnpackV1",
                source_locator="bare-course",
                generator_version_id=version_id,
                consumable_url=CONSUMABLE,
            )
        )
    cleanup["contents"].append(registration.content.id)

    assert registration.created


def test_unknown_never_conflicts_with_a_declared_generator(cleanup, unique):
    """ADR-0024 cl. 1: `unknown` is legitimate even when the package declares a generator —
    only a specific, disagreeing selection is refused."""
    with SessionLocal() as s:
        registration = use_case_declaring(s, f"Unregistered Generator {unique}", "9.9.9")(
            RegisterPackageFromSourceCommand(
                package_format="LearnpackV1",
                source_locator="bare-course",
                generator_version_id=None,
                consumable_url=CONSUMABLE,
            )
        )
    cleanup["contents"].append(registration.content.id)

    assert registration.created


def test_a_selection_that_disagrees_with_the_declared_generator_is_refused(
    cleanup, register_generator_version, unique
):
    declared_id = register_generator_version(f"Declared Generator {unique}", "2.0.0")
    selected_id = register_generator_version(f"Other Generator {unique}", "1.0.0")

    with SessionLocal() as s:
        with pytest.raises(DeclaredGeneratorConflict) as excinfo:
            use_case_declaring(s, f"Declared Generator {unique}", "2.0.0")(
                RegisterPackageFromSourceCommand(
                    package_format="LearnpackV1",
                    source_locator="bare-course",
                    generator_version_id=selected_id,
                    consumable_url=CONSUMABLE,
                )
            )

    exc = excinfo.value
    assert exc.declared_name == f"Declared Generator {unique}"
    assert exc.declared_version == "2.0.0"
    assert exc.resolved_id == declared_id
    assert exc.selected_id == selected_id


def test_a_declared_generator_with_no_registered_match_is_refused_when_something_is_selected(
    cleanup, register_generator_version, unique
):
    selected_id = register_generator_version(f"Some Generator {unique}", "1.0.0")

    with SessionLocal() as s:
        with pytest.raises(DeclaredGeneratorConflict) as excinfo:
            use_case_declaring(s, f"Unregistered Generator {unique}", "9.9.9")(
                RegisterPackageFromSourceCommand(
                    package_format="LearnpackV1",
                    source_locator="bare-course",
                    generator_version_id=selected_id,
                    consumable_url=CONSUMABLE,
                )
            )

    assert excinfo.value.resolved_id is None
