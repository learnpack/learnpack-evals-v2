"""The completion policy replayed directly (ADR-0003 idempotency).

The dispatcher may re-deliver an event, and a failed policy can be reprocessed from the
`events` table. Doing so must not record a completion twice nor re-publish the event.
"""

import pytest
from sqlalchemy import text

from app.modules.orchestration.infrastructure.policies import on_evaluation_submitted
from app.shared.domain.events import DomainEvent

RUBRIC = "learnpack-pedagogical-v1"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"
CRITERIA = [
    "objectives-quality",
    "constructive-alignment",
    "instructional-design",
    "inter-lesson-coherence",
    "learning-progression",
]


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


def _count(session, sql: str, params: dict) -> int:
    return session.execute(text(sql), params).scalar_one()


def test_replaying_the_event_is_idempotent(admin, as_user, cleanup, unique, session):
    content_id = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"course-{unique}",
            "consumable_url": COURSE_URL,
            "generator_version_id": None,
            "metadata": {"learningObjectives": ["x"], "targetAudience": "y"},
        },
    ).json()["content_id"]
    cleanup["contents"].append(content_id)

    campaign_id = admin.post(
        "/admin/campaigns",
        json={
            "instrument_version_id": RUBRIC,
            "required_evaluations_per_content": 1,
            "content_ids": [content_id],
        },
    ).json()["campaign_id"]
    cleanup["campaigns"].append(campaign_id)

    ada = as_user(f"user_ada_{unique}", f"ada-{unique}@example.com", "Ada")
    ada_id = ada.get("/me").json()["assessor_id"]
    cleanup["assessors"].append(ada_id)

    assignment_id = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": ada_id},
    ).json()["assignment_id"]

    ada.post(
        "/evaluations",
        json={
            "assignment_id": assignment_id,
            "scores": [{"criterion_id": c, "score": 4} for c in CRITERIA],
        },
    )

    completions_sql = "SELECT count(*) FROM content_evaluation_completions WHERE campaign_id = :c"
    events_sql = (
        "SELECT count(*) FROM events "
        "WHERE event_type = 'ContentEvaluationCompleted' AND aggregate_id = :c"
    )
    assert _count(session, completions_sql, {"c": campaign_id}) == 1
    assert _count(session, events_sql, {"c": campaign_id}) == 1

    # Replay the *stored* event, exactly as reprocessing from the `events` table would —
    # rather than a hand-built payload, which could drift from what is really published.
    stored = (
        session.execute(
            text(
                """
            SELECT aggregate_type, aggregate_id, payload FROM events
             WHERE event_type = 'EvaluationSubmitted'
               AND payload->>'contentId' = :content_id
            """
            ),
            {"content_id": content_id},
        )
        .mappings()
        .one()
    )

    replayed = DomainEvent(
        event_type="EvaluationSubmitted",
        aggregate_type=stored["aggregate_type"],
        aggregate_id=stored["aggregate_id"],
        payload=stored["payload"],
    )
    on_evaluation_submitted(replayed)
    on_evaluation_submitted(replayed)

    session.commit()  # drop this session's snapshot before re-reading
    assert _count(session, completions_sql, {"c": campaign_id}) == 1
    assert _count(session, events_sql, {"c": campaign_id}) == 1

    # And the assignment is still submitted exactly once.
    status = session.execute(
        text("SELECT status FROM assignments WHERE id = :id"), {"id": assignment_id}
    ).scalar_one()
    assert status == "submitted"
