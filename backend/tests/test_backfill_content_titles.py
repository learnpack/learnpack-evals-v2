"""Recovering the name of a course registered before the title was kept (ADR-0059).

A migration that happens to need a profile: the value it writes is the one the profile
already extracted from the same package, and running it twice writes nothing the second
time. Everything here goes through the CLI entry point, because that is the only caller.
"""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.cli import run_backfill_content_titles
from app.modules.content_profiling.application.profile_content import (
    ProfileContent,
    ProfileContentCommand,
)
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.modules.content_profiling.infrastructure.gateways import (
    DesignNamespaceGateway,
    RegistryContentGateway,
)
from app.modules.content_profiling.infrastructure.repository import SqlAlchemyProfileRepository
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from tests.conftest import fixture_artifact_rows

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"


@pytest.fixture
def unnamed_course(cleanup, unique):
    """A course registered by hand: its package declares `Bare Course`, and the row has no
    title, which is exactly the state every course registered before ADR-0059 is in."""
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = RegisterContentVersion(
            contents=SqlAlchemyContentRepository(session),
            briefs=SqlAlchemyBriefRepository(session),
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )
        content = use_case(
            RegisterContentVersionCommand(
                package_format="LearnpackV1",
                external_id=f"unnamed-course-{unique}",
                artifacts=fixture_artifact_rows("bare-course"),
                generator_version_id=None,
            )
        )
    cleanup["contents"].append(content.id)
    assert content.title is None
    return content.id


def profile(content_id) -> None:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        ProfileContent(
            profiles=SqlAlchemyProfileRepository(session),
            contents=RegistryContentGateway(session),
            namespace=DesignNamespaceGateway(session),
            adapters=ADAPTERS_BY_FORMAT,
            fetcher=FilesystemPackageFetcher(FIXTURES),
            publisher=uow.events,
            uow=uow,
        )(ProfileContentCommand(content_id=content_id))


def title_of(session, content_id) -> str | None:
    return session.execute(
        text("SELECT title FROM contents WHERE id = :id"), {"id": content_id}
    ).scalar()


def test_the_name_is_recovered_from_the_profile(requires_db, namespace, unnamed_course, session):
    profile(unnamed_course)

    assert run_backfill_content_titles([str(unnamed_course)]) == 0
    assert title_of(session, unnamed_course) == "Bare Course"


def test_running_it_again_writes_nothing(requires_db, namespace, unnamed_course, session):
    profile(unnamed_course)
    run_backfill_content_titles([str(unnamed_course)])

    assert run_backfill_content_titles([str(unnamed_course)]) == 0
    assert title_of(session, unnamed_course) == "Bare Course"


def test_a_course_with_no_profile_is_left_unnamed(requires_db, unnamed_course, session):
    """Nothing is invented from the slug: an unprofiled course keeps its null until
    somebody profiles it and runs this again."""
    assert run_backfill_content_titles([str(unnamed_course)]) == 0
    assert title_of(session, unnamed_course) is None


def test_an_unreadable_content_id_is_refused():
    assert run_backfill_content_titles(["not-a-uuid"]) == 1
