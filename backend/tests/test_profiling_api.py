"""Read-only profiling endpoints — the designer's workbench feed (ADR-0012)."""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.modules.content_profiling.application.profile_content import (
    ProfileContent,
    ProfileContentCommand,
)
from app.modules.content_profiling.infrastructure.adapters import (
    ADAPTERS_BY_FORMAT,
    learnpack_v1,
)
from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher
from app.modules.content_profiling.infrastructure.gateways import (
    DesignNamespaceGateway,
    RegistryContentGateway,
)
from app.modules.content_profiling.infrastructure.repository import (
    SqlAlchemyAcceptanceRepository,
    SqlAlchemyProfileRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork
from app.shared.domain.ids import new_id

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"
REQUIREMENT_IDS = (
    "learning_objectives",
    "target_audience",
    "prerequisites",
    "practice_exercises",
)


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def namespace(cleanup):
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
def profiled_content(admin, cleanup, unique, namespace):
    content_id = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"viewer-course-{unique}",
            "consumable_url": "https://viewer.learn-pack.com/",
            "metadata": {
                "learningObjectives": ["Explain the viewer"],
                "targetAudience": "The team",
            },
        },
    ).json()["content_id"]
    cleanup["contents"].append(content_id)
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
    return content_id


def test_profiles_are_admin_only(as_user, cleanup, unique):
    evaluator = as_user(f"user_eval_{unique}", f"eval-{unique}@example.com", "Eva")
    cleanup["assessors"].append(evaluator.get("/me").json()["assessor_id"])
    assert evaluator.get("/admin/profiles").status_code == 403
    assert evaluator.get("/admin/profiling/capabilities").status_code == 403


def test_profile_viewer_serves_cited_entries(admin, profiled_content, unique):
    listed = admin.get("/admin/profiles").json()
    mine = next(p for p in listed if p["content_id"] == str(profiled_content))
    assert mine["external_id"] == f"viewer-course-{unique}"
    assert mine["status"] == "ok"

    detail = admin.get(f"/admin/contents/{profiled_content}/profile").json()
    entries = {e["data_requirement_id"]: e for e in detail["entries"]}
    assert set(entries) == set(REQUIREMENT_IDS)
    objectives = entries["learning_objectives"]
    assert objectives["provenance"] == "declared_structured"
    assert "Explain the viewer" in objectives["quote"]
    assert objectives["locator"] == {"source": "metadata", "key": "learningObjectives"}
    # Explicit absence travels to the workbench too (ADR-0009 §4).
    assert entries["practice_exercises"]["provenance"] == "absent"
    assert entries["practice_exercises"]["quote"] is None


def test_missing_profile_is_404(admin):
    assert admin.get(f"/admin/contents/{new_id()}/profile").status_code == 404


def test_capabilities_expose_the_acceptance_state(admin, cleanup, session):
    before = admin.get("/admin/profiling/capabilities").json()
    learnpack = next(c for c in before if c["package_format"] == "LearnpackV1")
    assert learnpack["adapter_version"] == learnpack_v1.ADAPTER_VERSION
    assert set(learnpack["capabilities"]) == set(REQUIREMENT_IDS)
    assert learnpack["accepted"] is False

    cleanup["acceptances"].append(("LearnpackV1", learnpack_v1.ADAPTER_VERSION))
    SqlAlchemyAcceptanceRepository(session).accept(
        "LearnpackV1", learnpack_v1.ADAPTER_VERSION, new_id()
    )
    session.commit()

    after = admin.get("/admin/profiling/capabilities").json()
    assert next(c for c in after if c["package_format"] == "LearnpackV1")["accepted"] is True
