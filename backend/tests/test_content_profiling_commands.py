"""ProfileContent / AcceptExtraction against the real store (13-code-qa §3.4)."""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.modules.content_profiling.application.accept_extraction import (
    AcceptExtraction,
    AcceptExtractionCommand,
)
from app.modules.content_profiling.application.profile_content import (
    ProfileAlreadyExists,
    ProfileContent,
    ProfileContentCommand,
)
from app.modules.content_profiling.domain.profile import InvalidProfile
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.modules.content_profiling.infrastructure.gateways import (
    DesignNamespaceGateway,
    RegistryContentGateway,
)
from app.modules.content_profiling.infrastructure.repository import (
    SqlAlchemyAcceptanceRepository,
    SqlAlchemyProfileRepository,
)
from app.modules.evaluand_registry.application.register_content_version import (
    RegisterContentVersion,
    RegisterContentVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyBriefRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyGeneratorVersionRepository,
    SqlAlchemyMetadataSchemaRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.domain.ids import new_id

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"
REQUIREMENT_IDS = (
    "learning_objectives",
    "target_audience",
    "prerequisites",
    "lesson_inventory",
    "lesson_bodies",
    "lesson_activities",
)


@pytest.fixture
def namespace(cleanup):
    """Mint the canonical ids the adapter conforms to (normally the instrument import's job)."""
    with SessionLocal() as session:
        for requirement_id in REQUIREMENT_IDS:
            session.execute(
                text(
                    "INSERT INTO data_requirements (id, definition) "
                    "VALUES (:id, :definition) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": requirement_id, "definition": f"test definition of {requirement_id}"},
            )
            cleanup["data_requirements"].append(requirement_id)
        session.commit()


@pytest.fixture
def register_content(cleanup, unique):
    def _register(artifacts: list[dict] | None = None, metadata: dict | None = None):
        with SessionLocal() as session:
            uow = UnitOfWork(session)
            use_case = RegisterContentVersion(
                contents=SqlAlchemyContentRepository(session),
                schemas=SqlAlchemyMetadataSchemaRepository(session),
                briefs=SqlAlchemyBriefRepository(session),
                generators=SqlAlchemyGeneratorVersionRepository(session),
                publisher=uow.events,
                uow=uow,
            )
            content = use_case(
                RegisterContentVersionCommand(
                    package_format="LearnpackV1",
                    external_id=f"profiled-course-{unique}",
                    consumable_url=f"https://profiled-{unique}.learn-pack.com/",
                    metadata=metadata
                    if metadata is not None
                    else {
                        "learningObjectives": ["Explain how profiling works"],
                        "targetAudience": "Developers of this very engine",
                    },
                    artifacts=artifacts or [],
                )
            )
        cleanup["contents"].append(content.id)
        return content.id

    return _register


def profile_content_use_case(session) -> ProfileContent:
    uow = UnitOfWork(session)
    return ProfileContent(
        profiles=SqlAlchemyProfileRepository(session),
        contents=RegistryContentGateway(session),
        namespace=DesignNamespaceGateway(session),
        adapters=ADAPTERS_BY_FORMAT,
        fetcher=FilesystemPackageFetcher(FIXTURES),
        publisher=uow.events,
        uow=uow,
    )


def profile_rows(session, content_id):
    return (
        session.execute(
            text("SELECT id, status, error FROM content_profiles WHERE content_id = :id"),
            {"id": content_id},
        )
        .mappings()
        .all()
    )


def events_for(session, aggregate_id) -> list[str]:
    return [
        row[0]
        for row in session.execute(
            text("SELECT event_type FROM events WHERE aggregate_id = :id ORDER BY id"),
            {"id": str(aggregate_id)},
        )
    ]


def test_profile_content_persists_cited_entries_and_event(
    requires_db, namespace, register_content, session
):
    content_id = register_content()

    with SessionLocal() as s:
        profile = profile_content_use_case(s)(ProfileContentCommand(content_id=content_id))

    assert profile.status == "ok"
    rows = (
        session.execute(
            text(
                "SELECT data_requirement_id, provenance, quote FROM profile_entries "
                "WHERE profile_id = :id ORDER BY data_requirement_id"
            ),
            {"id": profile.id},
        )
        .mappings()
        .all()
    )
    by_id = {row["data_requirement_id"]: row for row in rows}
    assert set(by_id) == set(REQUIREMENT_IDS)
    assert by_id["learning_objectives"]["provenance"] == "declared_structured"
    assert "profiling works" in by_id["learning_objectives"]["quote"]
    # No metadata entry and no artifacts: explicitly absent, quoteless (ADR-0009).
    assert by_id["prerequisites"]["provenance"] == "absent"
    assert by_id["lesson_inventory"]["provenance"] == "absent"
    assert by_id["lesson_activities"]["provenance"] == "absent"
    assert by_id["lesson_activities"]["quote"] is None
    assert events_for(session, profile.id) == ["ContentProfiled"]


def test_an_ok_profile_is_immutable_for_its_adapter_version(
    requires_db, namespace, register_content, session
):
    content_id = register_content()
    with SessionLocal() as s:
        profile_content_use_case(s)(ProfileContentCommand(content_id=content_id))
    with SessionLocal() as s:
        with pytest.raises(ProfileAlreadyExists):
            profile_content_use_case(s)(ProfileContentCommand(content_id=content_id))
    assert len(profile_rows(session, content_id)) == 1


def test_a_failed_profile_records_the_error_and_can_be_retried(
    requires_db, namespace, register_content, session
):
    content_id = register_content(
        artifacts=[
            {
                "kind": "package_manifest",
                "locator": "broken-course/.learn/package-manifest.json",
            }
        ]
    )

    with SessionLocal() as s:
        first = profile_content_use_case(s)(ProfileContentCommand(content_id=content_id))
    assert first.status == "failed"
    assert "JSON" in (first.error or "")
    assert events_for(session, first.id) == ["ContentProfilingFailed"]

    # The manual path replaces a failed profile in place (the one immutability exception).
    with SessionLocal() as s:
        second = profile_content_use_case(s)(ProfileContentCommand(content_id=content_id))
    rows = profile_rows(session, content_id)
    assert [row["id"] for row in rows] == [second.id]
    assert second.id != first.id


def test_acceptance_is_idempotent_and_emits_once(requires_db, cleanup, session):
    adapter = ADAPTERS_BY_FORMAT["LearnpackV1"]
    cleanup["acceptances"].append(("LearnpackV1", adapter.adapter_version))
    command = AcceptExtractionCommand(
        package_format="LearnpackV1",
        adapter_version=adapter.adapter_version,
        accepted_by=new_id(),
    )

    outcomes = []
    for _ in range(2):
        with SessionLocal() as s:
            uow = UnitOfWork(s)
            use_case = AcceptExtraction(
                acceptances=SqlAlchemyAcceptanceRepository(s), publisher=uow.events, uow=uow
            )
            outcomes.append(use_case(command))

    assert outcomes == [True, False]
    assert events_for(session, f"LearnpackV1:{adapter.adapter_version}") == ["ExtractionAccepted"]


def test_profiling_without_the_canonical_namespace_is_a_hard_error(
    requires_db, register_content, session
):
    """Conformist (ADR-0014): capabilities must exist in Design's namespace — an empty
    namespace means the instrument was never imported, and that is a bug, not a profile."""
    content_id = register_content()
    with SessionLocal() as s:
        with pytest.raises(InvalidProfile, match="namespace"):
            profile_content_use_case(s)(ProfileContentCommand(content_id=content_id))
    assert profile_rows(session, content_id) == []
