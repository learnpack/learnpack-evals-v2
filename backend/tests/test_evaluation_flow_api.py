"""The human backbone end to end, and the quorum policy (ADR-0002 · 08-code.md §11).

Covers the two cases 08-code.md §11 calls out explicitly: a reassignment, and one evaluation
satisfying two campaigns.
"""

from uuid import UUID

import pytest
from conftest import declare_dataset_over, open_campaign_over
from sqlalchemy import text

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


def scores(**overrides) -> list[dict]:
    return [{"quality_id": c, "score": overrides.get(c, 4)} for c in QUALITIES]


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
            "generator_version_id": None,
        },
    ).json()
    cleanup["contents"].append(body["content_id"])
    return body["content_id"]


@pytest.fixture
def make_campaign(admin, cleanup, content):
    def _make(required: int = 2):
        return open_campaign_over(
            admin,
            cleanup,
            [content],
            name="Evaluation flow campaign",
            instrument_version_id=RUBRIC,
            required_evaluations_per_content=required,
        )["campaign_id"]

    return _make


def assign(admin, campaign_id, content_id, assessor_id):
    response = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": assessor_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["assignment_id"]


# --------------------------------------------------------------------------- flow


def test_the_evaluator_reads_the_course_by_name(admin, evaluator, content, make_campaign, session):
    """ADR-0059 §5: the name the package declares, and nothing that could say who generated
    the course. The row is named directly here — the fixture registers by hand, and a hand
    path never names a course (§1)."""
    session.execute(
        text("UPDATE contents SET title = :title WHERE id = :id"),
        {"title": "Introduction to Generative AI", "id": content},
    )
    session.commit()

    campaign_id = make_campaign(required=1)
    client, assessor_id = evaluator("grace")
    assignment_id = assign(admin, campaign_id, content, assessor_id)

    listed = client.get("/me/assignments").json()[0]
    assert listed["content_title"] == "Introduction to Generative AI"
    assert "external_id" not in listed

    detail = client.get(f"/assignments/{assignment_id}").json()
    assert detail["content_title"] == "Introduction to Generative AI"
    assert "external_id" not in detail


def test_a_course_with_no_declared_name_says_so(admin, evaluator, content, make_campaign):
    """Null travels rather than being papered over with the external id, which is what the
    screen would otherwise fall back to and must not."""
    campaign_id = make_campaign(required=1)
    client, assessor_id = evaluator("hopper")
    assignment_id = assign(admin, campaign_id, content, assessor_id)

    assert client.get("/me/assignments").json()[0]["content_title"] is None
    assert client.get(f"/assignments/{assignment_id}").json()["content_title"] is None


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
    assert [c["quality_id"] for c in detail["items"]] == QUALITIES
    assert detail["scale_min"] == 1 and detail["scale_max"] == 5
    assert detail["response_format"] == "likert"

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


def test_an_answer_given_to_one_campaign_is_not_a_delivery_to_another(
    admin, evaluator, content, make_campaign, session
):
    """An evaluation answers one assignment (ADR-0065).

    Ada is asked the same course by two rounds and answers the first. The second asked her
    too and received nothing, so it says so — before ADR-0065 its assignment flipped to
    submitted and its progress screen credited it with work it never got.
    """
    first_campaign = make_campaign(required=1)
    second_campaign = make_campaign(required=1)
    ada, ada_id = evaluator("ada")

    first_assignment = assign(admin, first_campaign, content, ada_id)
    assign(admin, second_campaign, content, ada_id)

    ada.post("/evaluations", json={"assignment_id": first_assignment, "scores": scores()})

    assert (
        admin.get(f"/admin/campaigns/{first_campaign}/progress").json()["contents"][0]["completed"]
        is True
    )
    assert (
        admin.get(f"/admin/campaigns/{second_campaign}/progress").json()["contents"][0]["completed"]
        is False
    )

    # One submission, one evaluation: the second round has to ask again to get one.
    evaluations = session.execute(
        text("SELECT count(*) FROM evaluations WHERE content_id = :c"), {"c": content}
    ).scalar_one()
    assert evaluations == 1


def test_the_second_round_gets_its_own_answer_and_neither_moves_the_other(
    admin, evaluator, content, make_campaign, session
):
    """The defect ADR-0065 closes, in the order that produced it.

    A campaign that has already been answered, a second one opened afterwards over the same
    course and expert, and a fresh answer to it. Before this, the later answer became what
    BOTH rounds counted, and the first stopped saying what it found when it ran.
    """
    first_campaign = make_campaign(required=1)
    ada, ada_id = evaluator("ada")
    first_assignment = assign(admin, first_campaign, content, ada_id)
    ada.post(
        "/evaluations",
        json={"assignment_id": first_assignment, "scores": scores(**{"alignment-coverage": 1})},
    )

    second_campaign = make_campaign(required=1)
    second_assignment = assign(admin, second_campaign, content, ada_id)
    ada.post(
        "/evaluations",
        json={"assignment_id": second_assignment, "scores": scores(**{"alignment-coverage": 5})},
    )

    def coverage(campaign_id: str) -> float:
        report = admin.get(f"/admin/campaigns/{campaign_id}/report").json()
        row = next(i for i in report["items"] if i["quality_id"] == "alignment-coverage")
        return row["summary"]["average"]

    assert coverage(first_campaign) == 1.0
    assert coverage(second_campaign) == 5.0


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
            "name": "Campaign over an unpublished instrument",
            "instrument_version_id": "does-not-exist",
            "required_evaluations_per_content": 1,
            "dataset_version_id": declare_dataset_over(admin, cleanup, [content]),
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
            "generator_version_id": None,
        },
    ).json()
    cleanup["contents"].append(other["content_id"])

    response = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": other["content_id"], "assessor_id": ada_id},
    )
    assert response.status_code == 422


@pytest.fixture
def undeployed_campaign(admin, cleanup, unique):
    """A campaign over one course that declares no deployed instance."""

    def _make():
        undeployed = admin.post(
            "/admin/contents",
            json={
                "package_format": "LearnpackV1",
                "external_id": f"undeployed-{unique}",
                "generator_version_id": None,
            },
        ).json()
        cleanup["contents"].append(undeployed["content_id"])
        campaign = open_campaign_over(
            admin,
            cleanup,
            [undeployed["content_id"]],
            name="Campaign over an undeployed course",
            instrument_version_id=RUBRIC,
        )
        return campaign["campaign_id"], undeployed["content_id"]

    return _make


def test_a_course_with_no_deployed_instance_cannot_be_assigned(
    admin, evaluator, undeployed_campaign
):
    """ADR-0068, which closes the guard ADR-0028 §5 deferred by name. The course stays a
    complete evaluand for the automated path; what it cannot take is a human."""
    campaign_id, content_id = undeployed_campaign()
    _, ada_id = evaluator("ada")

    refused = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": ada_id},
    )
    assert refused.status_code == 422, refused.text
    assert "deployed" in refused.json()["detail"]


def test_declaring_the_deployment_makes_the_course_assignable(
    admin, evaluator, undeployed_campaign
):
    """The refusal is repairable, which is what ADR-0054 changed and what made enforcing it
    safe: declare the deployment, assign again."""
    campaign_id, content_id = undeployed_campaign()
    _, ada_id = evaluator("ada")

    declared = admin.post(
        f"/admin/contents/{content_id}/consumable-url", json={"consumable_url": COURSE_URL}
    )
    assert declared.status_code == 200, declared.text

    assign(admin, campaign_id, content_id, ada_id)


def test_an_assignment_made_before_the_rule_still_reads_as_null(
    admin, evaluator, undeployed_campaign, session
):
    """The end of the read path (ADR-0028 §4): registry snapshot → assignment detail. Such a
    row can no longer be created through the act (ADR-0068), and the ones already in the store
    still have to be read — so it is written straight to the repository, which is what having
    predated the rule looks like."""
    from app.modules.orchestration.domain.assignment import Assignment
    from app.modules.orchestration.infrastructure.repository import SqlAlchemyAssignmentRepository
    from app.shared.domain.ids import new_id

    campaign_id, content_id = undeployed_campaign()
    client, assessor_id = evaluator("ada")

    assignment = Assignment(
        id=new_id(),
        campaign_id=UUID(campaign_id),
        content_id=UUID(content_id),
        assessor_id=UUID(assessor_id),
    )
    SqlAlchemyAssignmentRepository(session).add(assignment)
    session.commit()

    detail = client.get(f"/assignments/{assignment.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["consumable_url"] is None


def _register_automated(session, cleanup, unique: str) -> str:
    """An instrument package's identity row — the kind of assessor that is run, never asked."""
    from app.modules.identity.domain.assessor import Assessor, Kind
    from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
    from app.shared.domain.ids import new_id

    assessor = Assessor(
        id=new_id(),
        auth_provider=None,
        auth_subject=None,
        display_name=f"bot-{unique}",
        kind=Kind.AUTOMATED,
        source_config={
            "name": f"bot-{unique}",
            "version": "1",
            "instrumentId": "learnpack-pedagogical",
        },
    )
    SqlAlchemyAssessorRepository(session).add(assessor)
    session.commit()
    cleanup["assessors"].append(assessor.id)
    return str(assessor.id)


def test_an_automated_assessor_cannot_be_assigned_a_course(
    admin, content, make_campaign, session, cleanup, unique
):
    """ADR-0067: two kinds, two doors. It takes the defaults every assessor takes —
    `evaluator`, `active` — so nothing but this gate tells it apart from an expert."""
    campaign_id = make_campaign(required=1)
    bot_id = _register_automated(session, cleanup, unique)

    refused = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content, "assessor_id": bot_id},
    )
    assert refused.status_code == 422, refused.text
    assert "automated" in refused.json()["detail"]


def test_a_deactivated_evaluator_cannot_be_assigned_a_course(
    admin, evaluator, content, make_campaign
):
    """ADR-0051's "no new work" made true of the system and not only of the picker."""
    campaign_id = make_campaign(required=1)
    _, ada_id = evaluator("ada")
    left = admin.post(f"/admin/assessors/{ada_id}/active", json={"active": False})
    assert left.status_code == 200, left.text

    refused = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content, "assessor_id": ada_id},
    )
    assert refused.status_code == 422, refused.text
    assert "deactivated" in refused.json()["detail"]


def test_an_unknown_assessor_cannot_be_assigned_a_course(admin, content, make_campaign):
    """No foreign key says the id exists — `assessors` is another module's (ADR-0067 §2)."""
    campaign_id = make_campaign(required=1)

    refused = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content, "assessor_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert refused.status_code == 422, refused.text


def test_an_admin_can_be_assigned_a_course(admin, content, make_campaign):
    """ADR-0067 §3, the clause that would rot silently: the act refuses what is impossible,
    not who you would normally ask. An assessor holds one role, so requiring `evaluator`
    would lock an admin out of the instrument their own console runs."""
    campaign_id = make_campaign(required=1)
    admin_id = admin.get("/me").json()["assessor_id"]

    accepted = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content, "assessor_id": admin_id},
    )
    assert accepted.status_code == 201, accepted.text


def test_closed_campaign_rejects_new_assignments(admin, evaluator, content, make_campaign):
    campaign_id = make_campaign(required=1)
    _, ada_id = evaluator("ada")
    assert admin.post(f"/admin/campaigns/{campaign_id}/close").json()["status"] == "closed"

    response = admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content, "assessor_id": ada_id},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------- abstentions


def test_an_abstention_travels_as_a_null_score(admin, evaluator, content, make_campaign, session):
    """The off-scale answer of ADR-0052 §4, end to end: it covers its item, it
    persists as a null, and the report does not average it into anything."""
    campaign_id = make_campaign(required=1)
    client, assessor_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, assessor_id)
    client.post(f"/assignments/{assignment_id}/open")

    submitted = client.post(
        "/evaluations",
        json={
            "assignment_id": assignment_id,
            "scores": scores(**{QUALITIES[0]: None}),
        },
    )
    assert submitted.status_code == 201, submitted.text

    stored = session.execute(
        text("SELECT score FROM item_scores WHERE evaluation_id = :id AND quality_id = :c"),
        {"id": submitted.json()["evaluation_id"], "c": QUALITIES[0]},
    ).scalar_one()
    assert stored is None

    report = admin.get(f"/admin/campaigns/{campaign_id}/report").json()
    items = {i["quality_id"]: i["summary"] for i in report["items"]}
    # Still reported — the item WAS asked — but with no average, and counted as the
    # abstention it is rather than as an item nobody was put in front of (ADR-0060 §4).
    assert items[QUALITIES[0]]["average"] is None
    assert items[QUALITIES[0]]["abstentions"] == 1
    assert items[QUALITIES[0]]["withheld_contents"] == 0
    assert items[QUALITIES[1]]["average"] == 4.0


def test_an_omitted_score_field_is_refused(admin, evaluator, content, make_campaign):
    """Null is the abstention; a MISSING field is not. Silence is never evidence."""
    campaign_id = make_campaign(required=1)
    client, assessor_id = evaluator("ada")
    assignment_id = assign(admin, campaign_id, content, assessor_id)
    client.post(f"/assignments/{assignment_id}/open")

    payload = scores()
    payload[0].pop("score")

    refused = client.post("/evaluations", json={"assignment_id": assignment_id, "scores": payload})
    assert refused.status_code == 422, refused.text
