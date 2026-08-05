"""The auto-profiling policy: gated by the acceptance, idempotent under replay
(13-code-qa §3.4 · ADR-0003).

The end-to-end test registers through the API on purpose: the dispatcher swallows a
broken handler (it logs and keeps the event durable), so only observing the profile
row after a real `POST /admin/contents` proves the synchronous wiring works.
"""

import pytest
from sqlalchemy import text

from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.content_profiling.infrastructure.policies import on_content_version_registered
from app.platform.db import SessionLocal
from app.shared.domain.events import DomainEvent
from app.shared.domain.ids import new_id

REQUIREMENT_IDS = (
    "learning_objectives",
    "target_audience",
    "prerequisites",
    "lesson_inventory",
    "lesson_bodies",
    "lesson_activities",
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
def accept(cleanup, session):
    adapter = ADAPTERS_BY_FORMAT["LearnpackV1"]
    cleanup["acceptances"].append(("LearnpackV1", adapter.adapter_version))
    session.execute(
        text(
            "INSERT INTO extraction_acceptances (package_format, adapter_version, accepted_by) "
            "VALUES ('LearnpackV1', :version, :by) ON CONFLICT DO NOTHING"
        ),
        {"version": adapter.adapter_version, "by": new_id()},
    )
    session.commit()


def register(admin, cleanup, unique, suffix: str):
    content_id = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"course-{suffix}-{unique}",
            "consumable_url": "https://policy-test.learn-pack.com/",
        },
    ).json()["content_id"]
    cleanup["contents"].append(content_id)
    return content_id


def profile_count(session, content_id) -> int:
    return session.execute(
        text("SELECT count(*) FROM content_profiles WHERE content_id = :id"),
        {"id": content_id},
    ).scalar_one()


def profiled_events(session, content_id) -> int:
    return session.execute(
        text(
            "SELECT count(*) FROM events WHERE event_type = 'ContentProfiled' "
            "AND payload->>'contentId' = :id"
        ),
        {"id": str(content_id)},
    ).scalar_one()


def stored_registration_event(session, content_id) -> DomainEvent:
    stored = (
        session.execute(
            text(
                "SELECT aggregate_type, aggregate_id, payload FROM events "
                "WHERE event_type = 'ContentVersionRegistered' AND aggregate_id = :id"
            ),
            {"id": str(content_id)},
        )
        .mappings()
        .one()
    )
    return DomainEvent(
        event_type="ContentVersionRegistered",
        aggregate_type=stored["aggregate_type"],
        aggregate_id=stored["aggregate_id"],
        payload=stored["payload"],
    )


def test_without_acceptance_registration_profiles_nothing(
    admin, cleanup, unique, session, namespace
):
    content_id = register(admin, cleanup, unique, "unaccepted")
    assert profile_count(session, content_id) == 0

    # Replaying the stored event by hand changes nothing either.
    on_content_version_registered(stored_registration_event(session, content_id))
    session.commit()
    assert profile_count(session, content_id) == 0


def test_with_acceptance_registration_profiles_synchronously_and_replay_is_idempotent(
    admin, cleanup, unique, session, namespace, accept
):
    content_id = register(admin, cleanup, unique, "accepted")

    # The POST alone left the profile: the policy ran inside the request's dispatch.
    assert profile_count(session, content_id) == 1
    assert profiled_events(session, content_id) == 1

    event = stored_registration_event(session, content_id)
    on_content_version_registered(event)
    on_content_version_registered(event)
    session.commit()
    assert profile_count(session, content_id) == 1
    assert profiled_events(session, content_id) == 1
