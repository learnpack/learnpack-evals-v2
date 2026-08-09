"""Registering from a source: discovery feeds the one canonical path (ADR-0027).

`RegisterContentVersion` stays the only writer of contents; what these tests pin is the
composition — descriptor and artifacts from discovery, brief from the discovered syllabus,
and the content-hash identity: unchanged → no-op, changed under the same declared version →
refused.
"""

import shutil
from pathlib import Path

import pytest
from sqlalchemy import text

from app.modules.evaluand_registry.application.ports import PackageDiscoveryError
from app.modules.evaluand_registry.application.register_content_version import (
    DuplicateContent,
    RegisterContentVersion,
)
from app.modules.evaluand_registry.application.register_package_from_source import (
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
    return RegisterPackageFromSource(PackageDiscovery(root_factory), register)


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
    assert content.consumable_url == CONSUMABLE
    assert content.content_hash
    # learn.json, package-manifest, two lesson bodies, one exercise file — no syllabus.
    assert registration.artifact_count == 5
    persisted = session.execute(
        text("SELECT count(*) FROM content_package_artifacts WHERE content_id = :id"),
        {"id": content.id},
    ).scalar()
    assert persisted == 5


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


def test_a_source_without_a_consumable_url_is_refused(cleanup, session):
    with SessionLocal() as s, pytest.raises(PackageDiscoveryError, match="consumable"):
        use_case(s)(
            RegisterPackageFromSourceCommand(
                package_format="LearnpackV1",
                source_locator="bare-course",
                generator_version_id=None,  # plain-prefixed root + no override → no URL
            )
        )


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
