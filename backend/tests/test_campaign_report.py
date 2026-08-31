"""The campaign report (ADR-0060), against Neon.

What is under test here is the **scoping** — which answers this campaign's numbers are made
of — and the shape of the payload. The arithmetic itself is checked by hand in
`test_campaign_aggregation.py`, against fakes.
"""

import uuid as _uuid

import pytest
from conftest import open_campaign_over

from app.modules.evaluation.domain.evaluation import CriterionScore, Evaluation
from app.modules.evaluation.infrastructure.repository import SqlAlchemyEvaluationRepository
from app.shared.domain.ids import new_id

RUBRIC = "learnpack-pedagogical-2.0.0"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"
CRITERIA = [
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


def scores(value: int = 4, **overrides) -> list[dict]:
    return [
        {"criterion_id": c, "score": overrides.get(c, value), "comment": None} for c in CRITERIA
    ]


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def evaluator(as_user, cleanup, unique):
    def _make(label: str):
        client = as_user(f"user_{label}_{unique}", f"{label}-{unique}@example.com", label)
        assessor_id = client.get("/me").json()["assessor_id"]
        cleanup["assessors"].append(assessor_id)
        return client, assessor_id

    return _make


@pytest.fixture
def make_content(admin, cleanup, unique):
    def _make(label: str = "course") -> str:
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
def content(make_content):
    return make_content()


@pytest.fixture
def campaign(admin, cleanup, content):
    return open_campaign_over(
        admin,
        cleanup,
        [content],
        name="First reference campaign",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=2,
    )["campaign_id"]


def assign(admin, campaign_id, content_id, assessor_id) -> str:
    return admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": assessor_id},
    ).json()["assignment_id"]


def submit(client, admin, campaign_id, content_id, assessor_id, **overrides):
    return client.post(
        "/evaluations",
        json={
            "assignment_id": assign(admin, campaign_id, content_id, assessor_id),
            "scores": scores(**overrides),
        },
    )


def report_of(admin, campaign_id) -> dict:
    response = admin.get(f"/admin/campaigns/{campaign_id}/report")
    assert response.status_code == 200, response.text
    return response.json()


def item(report: dict, criterion_id: str) -> dict:
    return next(i for i in report["items"] if i["criterion_id"] == criterion_id)


def course(report: dict, content_id: str) -> dict:
    return next(c for c in report["contents"] if c["content_id"] == content_id)


# ------------------------------------------------------------------------- the item axis


def test_the_report_reads_the_item_across_the_campaign(admin, evaluator, content, campaign):
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")

    # They agree on everything except `alignment-coverage`, where Ada says 2 and Bob says 5.
    submit(ada, admin, campaign, content, ada_id, **{"alignment-coverage": 2})
    submit(bob, admin, campaign, content, bob_id, **{"alignment-coverage": 5})

    report = report_of(admin, campaign)

    assert report["name"] == "First reference campaign"
    assert report["instrument"]["instrument_version_id"] == RUBRIC
    assert report["quorum"]["evaluations_counted"] == 2
    assert report["quorum"]["assessor_count"] == 2

    contested = item(report, "alignment-coverage")
    assert contested["summary"]["average"] == 3.5
    assert contested["summary"]["distribution"] == {"1": 0, "2": 1, "3": 0, "4": 0, "5": 1}
    assert contested["summary"]["agreement"]["pair_count"] == 1
    assert contested["summary"]["agreement"]["mean_abs_diff"] == 3.0
    assert contested["summary"]["agreement"]["exact_pct"] == 0.0
    assert contested["summary"]["agreement"]["within_one_pct"] == 0.0

    agreed = item(report, "instruction-demonstration")
    assert agreed["summary"]["agreement"]["exact_pct"] == 100.0


def test_every_item_of_the_pinned_instrument_is_listed(admin, campaign):
    """Including the ones nobody answered — a report of only what has data is a coverage
    lie (ADR-0060 §3)."""
    report = report_of(admin, campaign)

    assert {i["criterion_id"] for i in report["items"]} == set(CRITERIA)
    assert all(i["prompt"] for i in report["items"]), "an id is not a question"
    assert all(i["dimension"] for i in report["items"])

    untouched = item(report, "coherence-reinforcement")
    assert untouched["summary"]["average"] is None
    assert untouched["summary"]["scored_count"] == 0
    assert untouched["summary"]["agreement"]["pair_count"] == 0
    assert untouched["summary"]["agreement"]["exact_pct"] is None


def test_the_items_keep_the_order_the_instrument_gives_them(admin, campaign):
    report = report_of(admin, campaign)
    orders = [i["order"] for i in report["items"]]

    assert orders == sorted(orders)


# ----------------------------------------------------------------------------- scoping


def test_two_campaigns_over_the_same_course_do_not_pool(
    admin, evaluator, content, campaign, cleanup
):
    """The defect ADR-0060 closes: one course, two rounds, two panels, two answers."""
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")

    second = open_campaign_over(
        admin,
        cleanup,
        [content],
        name="Second round",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]

    submit(ada, admin, campaign, content, ada_id, **dict.fromkeys(CRITERIA, 2))
    submit(bob, admin, second, content, bob_id, **dict.fromkeys(CRITERIA, 5))

    first_report = report_of(admin, campaign)
    second_report = report_of(admin, second)

    # Pooled, every average would be 3.5 in both.
    assert item(first_report, "alignment-coverage")["summary"]["average"] == 2.0
    assert item(second_report, "alignment-coverage")["summary"]["average"] == 5.0
    assert first_report["quorum"]["evaluations_counted"] == 1
    assert second_report["quorum"]["evaluations_counted"] == 1


def test_one_evaluation_may_count_for_two_campaigns_that_asked_for_it(
    admin, evaluator, content, campaign, cleanup
):
    """The report filters, it does not partition (ADR-0060 §1).

    Ada is assigned the same course in both rounds; her single submission satisfies both,
    because the completion policy marks every open assignment that asked for it.
    """
    ada, ada_id = evaluator("ada")
    second = open_campaign_over(
        admin,
        cleanup,
        [content],
        name="Second round",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    assign(admin, second, content, ada_id)

    submit(ada, admin, campaign, content, ada_id)

    assert report_of(admin, campaign)["quorum"]["evaluations_counted"] == 1
    assert report_of(admin, second)["quorum"]["evaluations_counted"] == 1


def test_an_evaluation_this_campaign_never_asked_for_is_not_counted(
    admin, evaluator, content, campaign, session
):
    """The membership rule is the assignment (ADR-0060 §1).

    This is also why an automated evaluation can never appear: ADR-0034's assessors write
    into `evaluations` like everybody else, and no assignment ever names one — so there is no
    filter on assessor kind anywhere in the read model.
    """
    ada, ada_id = evaluator("ada")
    _, stranger_id = evaluator("stranger")

    submit(ada, admin, campaign, content, ada_id, **dict.fromkeys(CRITERIA, 4))

    unasked = Evaluation.submit(
        evaluation_id=new_id(),
        assessor_id=_uuid.UUID(stranger_id),
        content_id=_uuid.UUID(content),
        instrument_version_id=RUBRIC,
        scores=[CriterionScore(criterion_id=c, score=1) for c in CRITERIA],
        rubric_criterion_ids=CRITERIA,
    )
    SqlAlchemyEvaluationRepository(session).add(unasked)
    session.commit()

    report = report_of(admin, campaign)

    assert report["quorum"]["evaluations_counted"] == 1
    assert report["quorum"]["assessor_count"] == 1
    # Pooled, this would be (4 + 1) / 2 = 2.5.
    assert item(report, "alignment-coverage")["summary"]["average"] == 4.0
    assert len(course(report, content)["evaluations"]) == 1


def test_a_cancelled_assignment_does_not_pull_an_evaluation_into_its_campaign(
    admin, evaluator, content, campaign, cleanup
):
    """A campaign that withdrew its question does not get the answer somebody else asked for.

    The case is real rather than contrived: Bob is asked for the same course by two rounds,
    the first withdraws its request, and he answers the second. One evaluation exists, both
    campaigns are eligible for it by instrument and scope, and only the round that still asked
    may count it.
    """
    bob, bob_id = evaluator("bob")
    withdrawn = assign(admin, campaign, content, bob_id)
    assert admin.post(f"/admin/assignments/{withdrawn}/cancel").status_code == 200

    second = open_campaign_over(
        admin,
        cleanup,
        [content],
        name="Second round",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    submit(bob, admin, second, content, bob_id)

    first_report = report_of(admin, campaign)
    assert first_report["quorum"]["evaluations_counted"] == 0
    assert first_report["quorum"]["assessor_count"] == 0
    assert course(first_report, content)["evaluations"] == []

    assert report_of(admin, second)["quorum"]["evaluations_counted"] == 1


def test_a_repetition_is_shown_and_not_counted(admin, evaluator, content, campaign, session):
    """ADR-0005/0006: a human re-evaluation is a correction, not a second opinion."""
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")

    submit(ada, admin, campaign, content, ada_id, **dict.fromkeys(CRITERIA, 1))
    submit(bob, admin, campaign, content, bob_id, **dict.fromkeys(CRITERIA, 5))

    correction = Evaluation.submit(
        evaluation_id=new_id(),
        assessor_id=_uuid.UUID(ada_id),
        content_id=_uuid.UUID(content),
        instrument_version_id=RUBRIC,
        scores=[CriterionScore(criterion_id=c, score=3) for c in CRITERIA],
        rubric_criterion_ids=CRITERIA,
        attempt=2,
    )
    SqlAlchemyEvaluationRepository(session).add(correction)
    session.commit()

    report = report_of(admin, campaign)
    row = course(report, content)

    # (3 + 5) / 2 = 4.0, not (1 + 3 + 5) / 3 = 3.0
    assert item(report, "alignment-coverage")["summary"]["average"] == 4.0
    assert report["quorum"]["evaluations_counted"] == 2
    assert report["quorum"]["superseded_count"] == 1
    assert len(row["evaluations"]) == 3
    assert sum(1 for e in row["evaluations"] if e["superseded"]) == 1


# ------------------------------------------------------------------------ the silences


def test_the_three_silences_are_told_apart(admin, evaluator, make_content, cleanup, session):
    """Nobody asked · asked and could not judge · nobody has looked (ADR-0060 §4)."""
    judged = make_content("judged")
    untouched = make_content("untouched")
    campaign_id = open_campaign_over(
        admin,
        cleanup,
        [judged, untouched],
        name="Silences",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]

    ada, ada_id = evaluator("ada")
    # Ada abstains on `coherence-reinforcement` and answers everything else.
    ada.post(
        "/evaluations",
        json={
            "assignment_id": assign(admin, campaign_id, judged, ada_id),
            "scores": scores(4, **{"coherence-reinforcement": None}),
        },
    )

    # A course whose declaration is missing: nobody was asked, and the value was derived
    # (ADR-0053). Written straight through the repository — the mechanics that produce it are
    # tested in `test_withheld_items_flow.py`; what is under test here is how it reads.
    _, bob_id = evaluator("bob")
    assign(admin, campaign_id, untouched, bob_id)
    SqlAlchemyEvaluationRepository(session).add(
        Evaluation.submit(
            evaluation_id=new_id(),
            assessor_id=_uuid.UUID(bob_id),
            content_id=_uuid.UUID(untouched),
            instrument_version_id=RUBRIC,
            scores=[
                CriterionScore(criterion_id=c, score=1, derived=c == "objectives-observable")
                for c in CRITERIA
            ],
            rubric_criterion_ids=CRITERIA,
        )
    )
    session.commit()

    report = report_of(admin, campaign_id)

    abstained = item(report, "coherence-reinforcement")
    assert abstained["summary"]["abstentions"] == 1
    assert abstained["summary"]["withheld_contents"] == 0

    withheld = item(report, "objectives-observable")
    assert withheld["summary"]["withheld_contents"] == 1
    assert withheld["summary"]["abstentions"] == 0
    # The derived 1 is nobody's judgement, so it is not in the average of what humans said.
    assert withheld["summary"]["average"] == 4.0
    assert withheld["summary"]["answered_contents"] == 1

    # An item nobody was asked about on a course that was never submitted is neither.
    assert item(report, "alignment-coverage")["summary"]["withheld_contents"] == 0


def test_an_item_declares_what_it_rests_on(admin, campaign):
    """So the console can say *why* it was not asked, without a second fetch (ADR-0053)."""
    report = report_of(admin, campaign)

    assert item(report, "objectives-observable")["required_data"]
    assert item(report, "coherence-reinforcement")["required_data"] == []


# --------------------------------------------------------------------------- the course


def test_a_course_is_named_and_ranked_by_how_far_the_panel_was_apart(
    admin, evaluator, content, campaign, unique
):
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")
    submit(ada, admin, campaign, content, ada_id, **{"alignment-coverage": 2})
    submit(bob, admin, campaign, content, bob_id, **{"alignment-coverage": 5})

    row = course(report_of(admin, campaign), content)

    assert row["external_id"] == f"course-{unique}"
    assert row["submitted_count"] == 2
    assert row["required"] == 2
    assert row["completed"] is True
    assert row["disagreement"]["max_abs_diff"] == 3
    assert row["disagreement"]["contested_items"] == 1


def test_the_individual_answers_and_their_comments_reach_the_report(
    admin, evaluator, content, campaign
):
    ada, ada_id = evaluator("ada")
    ada.post(
        "/evaluations",
        json={
            "assignment_id": assign(admin, campaign, content, ada_id),
            "scores": [
                {
                    "criterion_id": c,
                    "score": 4,
                    "comment": "the objectives are not observable"
                    if c == "objectives-observable"
                    else None,
                }
                for c in CRITERIA
            ],
        },
    )

    individual = course(report_of(admin, campaign), content)["evaluations"][0]

    assert individual["assessor_name"] == "ada"
    assert individual["superseded"] is False
    comment = next(
        s["comment"] for s in individual["scores"] if s["criterion_id"] == "objectives-observable"
    )
    assert comment == "the objectives are not observable"


# ------------------------------------------------------------------------------ access


def test_the_report_requires_admin(as_user, cleanup, unique, admin, campaign):
    client = as_user(f"user_nosy_{unique}", f"nosy-{unique}@example.com", "Nosy")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    assert client.get(f"/admin/campaigns/{campaign}/report").status_code == 403


def test_an_unknown_campaign_has_no_report(admin):
    assert admin.get(f"/admin/campaigns/{_uuid.uuid4()}/report").status_code == 404


def test_the_report_issues_a_bounded_number_of_queries(admin, evaluator, content, campaign):
    """ADR-0006 requires batch reads: the count must not follow the size of the scope."""
    ada, ada_id = evaluator("ada")
    submit(ada, admin, campaign, content, ada_id)

    from sqlalchemy import event

    from app.platform.db import get_engine

    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert admin.get(f"/admin/campaigns/{campaign}/report").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    # The campaign is resolved by three different queries, each of which loads its scope;
    # then assignments, evaluations, scores, contents, assessors and the instrument. The
    # bound is about the ABSENCE of an N+1, not about this exact number — a per-content or
    # per-item read would leave it far behind.
    assert len(selects) <= 16, "\n".join(selects)
