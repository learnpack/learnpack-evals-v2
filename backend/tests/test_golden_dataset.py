"""Golden Dataset: the coverage rule (pure) and the full policy chain (against Neon).

The chain is the MVP's finish line (02-discover.md, bridge):
    EvaluationSubmitted → (orchestration) ContentEvaluationCompleted
                        → (golden) GoldenReferenceEstablished
"""

import pytest
from conftest import open_campaign_over
from sqlalchemy import text

from app.modules.golden_dataset.domain.golden_dataset import (
    GoldenReference,
    InvalidGoldenReference,
    is_usable,
)
from app.modules.golden_dataset.infrastructure.policies import on_content_evaluation_completed
from app.shared.domain.events import DomainEvent
from app.shared.domain.ids import new_id

RUBRIC = "learnpack-pedagogical-2.0.0"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"
QUALITIES = [
    "objectives-observable",
    "progression-starting-point",
    "alignment-coverage",
    "alignment-assessment",
    "instruction-authentic-problems",
    "instruction-demonstration",
    "instruction-prior-knowledge",
    "coherence-logical-sequence",
    "coherence-reinforcement",
    "coherence-explicit-links",
    "progression-prerequisites",
    "progression-cognitive-demand",
]


def scores(value: int = 4) -> list[dict]:
    return [{"quality_id": c, "score": value} for c in QUALITIES]


# --------------------------------------------------------------------------- pure


def test_coverage_rule():
    assert not is_usable(0.9, 1.0)
    assert is_usable(1.0, 1.0)  # exactly at the threshold counts
    assert is_usable(0.6, 0.5)


def test_reference_rejects_impossible_coverage():
    for coverage in (-0.1, 1.5):
        with pytest.raises(InvalidGoldenReference):
            GoldenReference(campaign_id=new_id(), instrument_version_id=RUBRIC, coverage=coverage)


def test_reference_requires_a_rubric_version():
    with pytest.raises(InvalidGoldenReference):
        GoldenReference(campaign_id=new_id(), instrument_version_id="", coverage=1.0)


# --------------------------------------------------------------------------- chain


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def make_content(admin, cleanup, unique):
    def _make(label: str) -> str:
        body = admin.post(
            "/admin/contents",
            json={
                "package_format": "LearnpackV1",
                "external_id": f"{label}-{unique}",
                "consumable_url": COURSE_URL,
                "generator_version_id": None,
                "metadata": {"learningObjectives": ["x"], "targetAudience": "y"},
            },
        ).json()
        cleanup["contents"].append(body["content_id"])
        return body["content_id"]

    return _make


@pytest.fixture
def evaluator(as_user, cleanup, unique):
    def _make(label: str):
        client = as_user(f"user_{label}_{unique}", f"{label}-{unique}@example.com", label)
        assessor_id = client.get("/me").json()["assessor_id"]
        cleanup["assessors"].append(assessor_id)
        return client, assessor_id

    return _make


def open_campaign(admin, cleanup, content_ids, required=1, threshold=1.0):
    return open_campaign_over(
        admin,
        cleanup,
        content_ids,
        name="Golden dataset campaign",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=required,
        golden_coverage_threshold=threshold,
    )["campaign_id"]


def submit(admin, client, campaign_id, content_id, assessor_id, value=4):
    assignment_id = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": assessor_id},
    ).json()["assignment_id"]
    response = client.post(
        "/evaluations", json={"assignment_id": assignment_id, "scores": scores(value)}
    )
    assert response.status_code == 201, response.text


def test_full_chain_establishes_the_golden_reference(
    admin, evaluator, make_content, cleanup, session
):
    content_id = make_content("course")
    campaign_id = open_campaign(admin, cleanup, [content_id], required=1)
    ada, ada_id = evaluator("ada")

    submit(admin, ada, campaign_id, content_id, ada_id)

    row = (
        session.execute(
            text(
                """
                SELECT coverage, established_at FROM golden_references
                 WHERE campaign_id = :c AND instrument_version_id = :r
                """
            ),
            {"c": campaign_id, "r": RUBRIC},
        )
        .mappings()
        .first()
    )
    assert row is not None, "the golden policy did not run"
    assert float(row["coverage"]) == 1.0
    assert row["established_at"] is not None

    # The whole chain is in the outbox, in order.
    published = (
        session.execute(
            text(
                """
                SELECT event_type FROM events
                 WHERE event_type IN ('EvaluationSubmitted', 'ContentEvaluationCompleted',
                                      'GoldenReferenceEstablished')
                   AND (payload->>'campaignId' = :c OR payload->>'contentId' = :co)
                 ORDER BY id
                """
            ),
            {"c": campaign_id, "co": content_id},
        )
        .scalars()
        .all()
    )
    assert published == [
        "EvaluationSubmitted",
        "ContentEvaluationCompleted",
        "GoldenReferenceEstablished",
    ]


def test_partial_coverage_does_not_establish_the_golden(
    admin, evaluator, make_content, cleanup, session
):
    first, second = make_content("first"), make_content("second")
    campaign_id = open_campaign(admin, cleanup, [first, second], required=1, threshold=1.0)
    ada, ada_id = evaluator("ada")

    submit(admin, ada, campaign_id, first, ada_id)

    status = admin.get(f"/admin/campaigns/{campaign_id}/golden").json()
    assert status["coverage"] == 0.5
    assert status["usable"] is False
    assert status["established_at"] is None

    # Completing the second content crosses the threshold.
    submit(admin, ada, campaign_id, second, ada_id)

    status = admin.get(f"/admin/campaigns/{campaign_id}/golden").json()
    assert status["coverage"] == 1.0
    assert status["usable"] is True
    assert status["established_at"] is not None


def test_a_lower_threshold_establishes_the_golden_earlier(admin, evaluator, make_content, cleanup):
    first, second = make_content("first"), make_content("second")
    campaign_id = open_campaign(admin, cleanup, [first, second], required=1, threshold=0.5)
    ada, ada_id = evaluator("ada")

    submit(admin, ada, campaign_id, first, ada_id)

    status = admin.get(f"/admin/campaigns/{campaign_id}/golden").json()
    assert status["coverage"] == 0.5
    assert status["usable"] is True
    assert status["established_at"] is not None


def test_replaying_the_event_does_not_duplicate_the_golden(
    admin, evaluator, make_content, cleanup, session
):
    content_id = make_content("course")
    campaign_id = open_campaign(admin, cleanup, [content_id], required=1)
    ada, ada_id = evaluator("ada")
    submit(admin, ada, campaign_id, content_id, ada_id)

    stored = (
        session.execute(
            text(
                """
                SELECT aggregate_type, aggregate_id, payload FROM events
                 WHERE event_type = 'ContentEvaluationCompleted'
                   AND payload->>'campaignId' = :c
                """
            ),
            {"c": campaign_id},
        )
        .mappings()
        .one()
    )
    replayed = DomainEvent(
        event_type="ContentEvaluationCompleted",
        aggregate_type=stored["aggregate_type"],
        aggregate_id=stored["aggregate_id"],
        payload=stored["payload"],
    )
    on_content_evaluation_completed(replayed)
    on_content_evaluation_completed(replayed)

    session.commit()
    references = session.execute(
        text("SELECT count(*) FROM golden_references WHERE campaign_id = :c"),
        {"c": campaign_id},
    ).scalar_one()
    events_published = session.execute(
        text(
            """
            SELECT count(*) FROM events
             WHERE event_type = 'GoldenReferenceEstablished'
               AND payload->>'campaignId' = :c
            """
        ),
        {"c": campaign_id},
    ).scalar_one()

    assert references == 1
    assert events_published == 1


def test_golden_status_of_unknown_campaign_is_404(admin):
    missing = "00000000-0000-0000-0000-000000000000"
    assert admin.get(f"/admin/campaigns/{missing}/golden").status_code == 404
