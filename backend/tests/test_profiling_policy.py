"""The auto-profiling policy: gated by the acceptance, idempotent under replay
(13-code-qa §3.4 · ADR-0003).

The end-to-end test registers through the API on purpose: the dispatcher swallows a
broken handler (it logs and keeps the event durable), so only observing the profile
row after a real `POST /admin/contents` proves the synchronous wiring works.
"""

import pytest
from sqlalchemy import text

from app.modules.content_profiling.infrastructure.policies import on_content_version_registered
from app.shared.domain.events import DomainEvent


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


def register(admin, cleanup, unique, suffix: str, artifacts: list | None = None):
    content_id = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"course-{suffix}-{unique}",
            "consumable_url": "https://policy-test.learn-pack.com/",
            "generator_version_id": None,
            "artifacts": artifacts or [],
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


def profiling_failed_events(session, content_id) -> int:
    return session.execute(
        text(
            "SELECT count(*) FROM events WHERE event_type = 'ContentProfilingFailed' "
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
    admin, cleanup, unique, session, namespace, accepted_extraction
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


def test_a_package_whose_locators_are_not_http_is_not_auto_profiled(
    admin, cleanup, unique, session, namespace, accepted_extraction
):
    """The automatic path fetches over http only (ADR-0029 §2). A filesystem-rooted package —
    the seeder's fixtures, `import-learnpack --base-dir` — is declined in silence: no row and
    no event, because a policy-written `failed` profile would be stuck on a readable package
    (the replay guard refuses ok AND failed)."""
    content_id = register(
        admin,
        cleanup,
        unique,
        "relative-locators",
        artifacts=[
            {"kind": "manifest", "locator": "bare-course/learn.json"},
            {"kind": "package_manifest", "locator": "bare-course/.learn/package-manifest.json"},
        ],
    )

    assert profile_count(session, content_id) == 0
    assert profiling_failed_events(session, content_id) == 0

    # And the replay finds the same answer, so nothing accumulates on a retry.
    on_content_version_registered(stored_registration_event(session, content_id))
    session.commit()
    assert profile_count(session, content_id) == 0


def test_a_package_with_no_artifacts_still_profiles(
    admin, cleanup, unique, session, namespace, accepted_extraction
):
    """The locator guard quantifies over the artifacts, so an empty package passes it
    vacuously (ADR-0029 §4): nothing to reach, all-`absent` entries, no network. `any` or an
    early return on an empty tuple would delete this behaviour."""
    content_id = register(admin, cleanup, unique, "no-artifacts")

    assert profile_count(session, content_id) == 1
    assert profiled_events(session, content_id) == 1
