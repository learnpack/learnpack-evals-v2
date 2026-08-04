"""The human backbone end to end, and the quorum policy (ADR-0002 · 08-code.md §11).

Covers the two cases 08-code.md §11 calls out explicitly: a reassignment, and one evaluation
satisfying two campaigns.
"""

import pytest
from sqlalchemy import text

RUBRIC = "learnpack-pedagogical-v1"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"
CRITERIA = [
    "objectives-quality",
    "constructive-alignment",
    "instructional-design",
    "inter-lesson-coherence",
    "learning-progression",
]


def scores(**overrides) -> list[dict]:
    return [{"criterion_id": c, "score": overrides.get(c, 4)} for c in CRITERIA]


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def evaluator(as_user, cleanup, unique):
    """Factory of evaluator clients — each returns (client, assessorId)."""

    def _make(label: str):
        client = as_user(f"user_{label}_{unique}", f"{label}-{unique}@example.com", label)
        assessor_id = client.get("/me").json()["assessor_id"]
        cleanup["assessors"].append(assessor_id)
        return client, assessor_id

    return _make


@pytest.fixture
def content(admin, cleanup, unique):
    body = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"course-{unique}",
            "consumable_url": COURSE_URL,
            "metadata": {
                "learningObjectives": ["Explain prompting"],
                "targetAudience": "Junior developers",
            },
        },
    ).json()
    cleanup["contents"].append(body["content_id"])
    return body["content_id"]


@pytest.fixture
def make_campaign(admin, cleanup, content):
    def _make(required: int = 2, metadata_view: list[str] | None = None):
        body = admin.post(
            "/admin/campaigns",
            json={
                "rubric_version_id": RUBRIC,
                "required_evaluations_per_content": required,
                "content_ids": [content],
                "metadata_view": metadata_view or [],
            },
        ).json()
        cleanup["campaigns"].append(body["campaign_id"])
        return body["campaign_id"]

    return _make


def assign(admin, campaign_id, content_id, assessor_id):
    response = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": assessor_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["assignment_id"]


# --------------------------------------------------------------------------- flow


def test_full_evaluator_flow(admin, evaluator, content, make_campaign, session):
    campaign_id = make_campaign(required=1)
    client, assessor_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, assessor_id)

    # 1. the assignment shows up in the to-do list
    pending = client.get("/me/assignments").json()
    assert [a["assignment_id"] for a in pending] == [assignment_id]

    # 2. the detail carries everything the 3-step UI needs
    detail = client.get(f"/assignments/{assignment_id}").json()
    assert detail["consumable_url"] == COURSE_URL
    assert [c["criterion_id"] for c in detail["criteria"]] == CRITERIA
    assert detail["scale_min"] == 1 and detail["scale_max"] == 5
    assert {e["key"] for e in detail["metadata"]} == {"learningObjectives", "targetAudience"}

    # 3. open, then submit
    assert client.post(f"/assignments/{assignment_id}/open").json()["status"] == "opened"
    submitted = client.post(
        "/evaluations",
        json={"assignment_id": assignment_id, "scores": scores()},
    )
    assert submitted.status_code == 201, submitted.text

    # the policy marked the assignment and it left the to-do list
    assert client.get("/me/assignments").json() == []

    progress = admin.get(f"/admin/campaigns/{campaign_id}/progress").json()
    assert progress["contents"][0] == {
        "content_id": content,
        "submitted_count": 1,
        "required": 1,
        "completed": True,
    }
    assert progress["coverage"] == 1.0


def test_metadata_view_filters_what_the_evaluator_sees(admin, evaluator, content, make_campaign):
    """Which keys are shown is the campaign's call (ADR-0001)."""
    campaign_id = make_campaign(required=1, metadata_view=["targetAudience"])
    client, assessor_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, assessor_id)

    detail = client.get(f"/assignments/{assignment_id}").json()
    assert [e["key"] for e in detail["metadata"]] == ["targetAudience"]


# --------------------------------------------------------------------------- quorum


def test_quorum_of_two_completes_on_the_second_submission(
    admin, evaluator, content, make_campaign, session
):
    campaign_id = make_campaign(required=2)
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")
    ada_assignment = assign(admin, campaign_id, content, ada_id)
    bob_assignment = assign(admin, campaign_id, content, bob_id)

    ada.post("/evaluations", json={"assignment_id": ada_assignment, "scores": scores()})
    progress = admin.get(f"/admin/campaigns/{campaign_id}/progress").json()
    assert progress["contents"][0]["completed"] is False

    bob.post("/evaluations", json={"assignment_id": bob_assignment, "scores": scores()})
    progress = admin.get(f"/admin/campaigns/{campaign_id}/progress").json()
    assert progress["contents"][0]["completed"] is True

    completions = session.execute(
        text(
            """
            SELECT count(*) FROM content_evaluation_completions
             WHERE campaign_id = :c AND content_id = :co
            """
        ),
        {"c": campaign_id, "co": content},
    ).scalar_one()
    assert completions == 1

    published = session.execute(
        text(
            """
                SELECT count(*) FROM events
                 WHERE event_type = 'ContentEvaluationCompleted' AND aggregate_id = :c
                """
        ),
        {"c": campaign_id},
    ).scalar_one()
    assert published == 1


def test_a_cancelled_assignment_does_not_count_towards_quorum(
    admin, evaluator, content, make_campaign
):
    """The reassignment case (ADR-0002, required by 08-code.md §11)."""
    campaign_id = make_campaign(required=2)
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")
    carol, carol_id = evaluator("carol")

    ada_assignment = assign(admin, campaign_id, content, ada_id)
    bob_assignment = assign(admin, campaign_id, content, bob_id)

    ada.post("/evaluations", json={"assignment_id": ada_assignment, "scores": scores()})

    # Bob never delivers → cancel and reassign to Carol.
    assert admin.post(f"/admin/assignments/{bob_assignment}/cancel").status_code == 200
    progress = admin.get(f"/admin/campaigns/{campaign_id}/progress").json()
    assert progress["contents"][0]["submitted_count"] == 1
    assert progress["contents"][0]["completed"] is False

    carol_assignment = assign(admin, campaign_id, content, carol_id)
    carol.post("/evaluations", json={"assignment_id": carol_assignment, "scores": scores()})

    progress = admin.get(f"/admin/campaigns/{campaign_id}/progress").json()
    assert progress["contents"][0]["submitted_count"] == 2
    assert progress["contents"][0]["completed"] is True


def test_one_evaluation_satisfies_two_campaigns(admin, evaluator, content, make_campaign, session):
    """Evaluation is campaign-agnostic; the assignment is the link (ADR-0002 · ADR-0005)."""
    first_campaign = make_campaign(required=1)
    second_campaign = make_campaign(required=1)
    ada, ada_id = evaluator("ada")

    first_assignment = assign(admin, first_campaign, content, ada_id)
    assign(admin, second_campaign, content, ada_id)

    # A single submission, made against the first campaign's assignment.
    ada.post("/evaluations", json={"assignment_id": first_assignment, "scores": scores()})

    for campaign_id in (first_campaign, second_campaign):
        progress = admin.get(f"/admin/campaigns/{campaign_id}/progress").json()
        assert progress["contents"][0]["completed"] is True, campaign_id

    # And only one evaluation was ever stored.
    evaluations = session.execute(
        text("SELECT count(*) FROM evaluations WHERE content_id = :c"), {"c": content}
    ).scalar_one()
    assert evaluations == 1


def test_over_quorum_is_allowed(admin, evaluator, content, make_campaign, session):
    campaign_id = make_campaign(required=2)
    clients = [evaluator(name) for name in ("ada", "bob", "carol")]

    for client, assessor_id in clients:
        assignment_id = assign(admin, campaign_id, content, assessor_id)
        response = client.post(
            "/evaluations", json={"assignment_id": assignment_id, "scores": scores()}
        )
        assert response.status_code == 201

    progress = admin.get(f"/admin/campaigns/{campaign_id}/progress").json()
    assert progress["contents"][0]["submitted_count"] == 3
    assert progress["contents"][0]["completed"] is True

    # Completion was recorded once, not once per extra submission.
    completions = session.execute(
        text("SELECT count(*) FROM content_evaluation_completions WHERE campaign_id = :c"),
        {"c": campaign_id},
    ).scalar_one()
    assert completions == 1


# --------------------------------------------------------------------------- guards


def test_resubmitting_the_same_assignment_is_a_conflict(admin, evaluator, content, make_campaign):
    """Human anti-duplication lives in the assignment (ADR-0005)."""
    campaign_id = make_campaign(required=1)
    ada, ada_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, ada_id)

    assert (
        ada.post(
            "/evaluations", json={"assignment_id": assignment_id, "scores": scores()}
        ).status_code
        == 201
    )
    second = ada.post("/evaluations", json={"assignment_id": assignment_id, "scores": scores()})
    assert second.status_code == 409


def test_cannot_submit_someone_elses_assignment(admin, evaluator, content, make_campaign):
    campaign_id = make_campaign(required=1)
    _, ada_id = evaluator("ada")
    bob, _ = evaluator("bob")
    assignment_id = assign(admin, campaign_id, content, ada_id)

    assert (
        bob.post(
            "/evaluations", json={"assignment_id": assignment_id, "scores": scores()}
        ).status_code
        == 403
    )
    assert bob.get(f"/assignments/{assignment_id}").status_code == 403


def test_incomplete_scores_are_rejected(admin, evaluator, content, make_campaign):
    campaign_id = make_campaign(required=1)
    ada, ada_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, ada_id)

    response = ada.post(
        "/evaluations", json={"assignment_id": assignment_id, "scores": scores()[:3]}
    )
    assert response.status_code == 422
    assert "missing" in response.json()["detail"]


def test_cannot_submit_a_cancelled_assignment(admin, evaluator, content, make_campaign):
    campaign_id = make_campaign(required=1)
    ada, ada_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, ada_id)
    admin.post(f"/admin/assignments/{assignment_id}/cancel")

    response = ada.post("/evaluations", json={"assignment_id": assignment_id, "scores": scores()})
    assert response.status_code == 409


def test_duplicate_active_assignment_is_a_conflict(admin, evaluator, content, make_campaign):
    campaign_id = make_campaign(required=2)
    _, ada_id = evaluator("ada")
    assign(admin, campaign_id, content, ada_id)

    duplicate = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content, "assessor_id": ada_id},
    )
    assert duplicate.status_code == 409


def test_reassigning_after_cancel_is_allowed(admin, evaluator, content, make_campaign):
    """Cancel frees the uniqueness slot — reassign = cancel + new (ADR-0002)."""
    campaign_id = make_campaign(required=1)
    _, ada_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, ada_id)
    admin.post(f"/admin/assignments/{assignment_id}/cancel")

    assert assign(admin, campaign_id, content, ada_id) != assignment_id


def test_a_submitted_assignment_cannot_be_cancelled(admin, evaluator, content, make_campaign):
    campaign_id = make_campaign(required=1)
    ada, ada_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, ada_id)
    ada.post("/evaluations", json={"assignment_id": assignment_id, "scores": scores()})

    assert admin.post(f"/admin/assignments/{assignment_id}/cancel").status_code == 409


def test_campaign_requires_a_published_rubric(admin, content, cleanup):
    response = admin.post(
        "/admin/campaigns",
        json={
            "rubric_version_id": "does-not-exist",
            "required_evaluations_per_content": 1,
            "content_ids": [content],
        },
    )
    assert response.status_code == 422


def test_cannot_assign_content_outside_the_campaign_scope(
    admin, evaluator, content, make_campaign, unique, cleanup
):
    campaign_id = make_campaign(required=1)
    _, ada_id = evaluator("ada")

    other = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"other-{unique}",
            "consumable_url": COURSE_URL,
            "metadata": {
                "learningObjectives": ["x"],
                "targetAudience": "y",
            },
        },
    ).json()
    cleanup["contents"].append(other["content_id"])

    response = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": other["content_id"], "assessor_id": ada_id},
    )
    assert response.status_code == 422


def test_closed_campaign_rejects_new_assignments(admin, evaluator, content, make_campaign):
    campaign_id = make_campaign(required=1)
    _, ada_id = evaluator("ada")
    assert admin.post(f"/admin/campaigns/{campaign_id}/close").json()["status"] == "closed"

    response = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content, "assessor_id": ada_id},
    )
    assert response.status_code == 422
