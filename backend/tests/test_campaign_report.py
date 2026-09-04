"""The campaign report (ADR-0060), against Neon.

What is under test here is the **scoping** — which answers this campaign's numbers are made
of — and the shape of the payload. The arithmetic itself is checked by hand in
`test_campaign_aggregation.py`, against fakes.
"""

import uuid as _uuid

import pytest
from conftest import open_campaign_over

from app.modules.evaluation.domain.evaluation import Evaluation, ItemScore
from app.modules.evaluation.infrastructure.repository import SqlAlchemyEvaluationRepository
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


def scores(value: int = 4, **overrides) -> list[dict]:
    return [{"quality_id": c, "score": overrides.get(c, value), "comment": None} for c in QUALITIES]


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


def item(report: dict, quality_id: str) -> dict:
    return next(i for i in report["items"] if i["quality_id"] == quality_id)


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

    assert {i["quality_id"] for i in report["items"]} == set(QUALITIES)
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

    submit(ada, admin, campaign, content, ada_id, **dict.fromkeys(QUALITIES, 2))
    submit(bob, admin, second, content, bob_id, **dict.fromkeys(QUALITIES, 5))

    first_report = report_of(admin, campaign)
    second_report = report_of(admin, second)

    # Pooled, every average would be 3.5 in both.
    assert item(first_report, "alignment-coverage")["summary"]["average"] == 2.0
    assert item(second_report, "alignment-coverage")["summary"]["average"] == 5.0
    assert first_report["quorum"]["evaluations_counted"] == 1
    assert second_report["quorum"]["evaluations_counted"] == 1


def test_an_answer_belongs_to_the_round_that_received_it_and_to_no_other(
    admin, evaluator, content, campaign, cleanup
):
    """An evaluation answers one assignment (ADR-0065).

    Ada is asked the same course by two rounds and answers one. The other asked and received
    nothing, and its report says so rather than borrowing an answer given elsewhere.
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
    assert report_of(admin, second)["quorum"]["evaluations_counted"] == 0


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

    submit(ada, admin, campaign, content, ada_id, **dict.fromkeys(QUALITIES, 4))

    unasked = Evaluation.submit(
        evaluation_id=new_id(),
        assessor_id=_uuid.UUID(stranger_id),
        content_id=_uuid.UUID(content),
        instrument_version_id=RUBRIC,
        scores=[ItemScore(quality_id=c, score=1) for c in QUALITIES],
        rubric_quality_ids=QUALITIES,
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


def test_an_evaluation_nobody_assigned_is_in_no_campaign(
    admin, evaluator, content, campaign, session
):
    """No assignment, no campaign (ADR-0065 §6).

    Written straight through the repository, so it answers nothing. Before ADR-0065 a row
    like this was pulled into the campaign by a lookup on `(content, assessor)` and shown as
    a correction of an answer it had nothing to do with.
    """
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")

    submit(ada, admin, campaign, content, ada_id, **dict.fromkeys(QUALITIES, 1))
    submit(bob, admin, campaign, content, bob_id, **dict.fromkeys(QUALITIES, 5))

    unasked = Evaluation.submit(
        evaluation_id=new_id(),
        assessor_id=_uuid.UUID(ada_id),
        content_id=_uuid.UUID(content),
        instrument_version_id=RUBRIC,
        scores=[ItemScore(quality_id=c, score=3) for c in QUALITIES],
        rubric_quality_ids=QUALITIES,
        attempt=2,
    )
    SqlAlchemyEvaluationRepository(session).add(unasked)
    session.commit()

    report = report_of(admin, campaign)
    row = course(report, content)

    # (1 + 5) / 2 = 3.0. The unasked 3 is in no round's arithmetic and on no row.
    assert item(report, "alignment-coverage")["summary"]["average"] == 3.0
    assert report["quorum"]["evaluations_counted"] == 2
    assert len(row["evaluations"]) == 2


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
    bobs_assignment = assign(admin, campaign_id, untouched, bob_id)
    SqlAlchemyEvaluationRepository(session).add(
        Evaluation.submit(
            evaluation_id=new_id(),
            assessor_id=_uuid.UUID(bob_id),
            content_id=_uuid.UUID(untouched),
            instrument_version_id=RUBRIC,
            scores=[
                ItemScore(quality_id=c, score=1, derived=c == "objectives-observable")
                for c in QUALITIES
            ],
            rubric_quality_ids=QUALITIES,
            # The shortcut still has to answer something: an evaluation with no assignment
            # is in no campaign (ADR-0065 §6), and this one is Bob answering his.
            assignment_id=_uuid.UUID(bobs_assignment),
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
                    "quality_id": c,
                    "score": 4,
                    "comment": "the objectives are not observable"
                    if c == "objectives-observable"
                    else None,
                }
                for c in QUALITIES
            ],
        },
    )

    individual = course(report_of(admin, campaign), content)["evaluations"][0]

    assert individual["assessor_name"] == "ada"
    comment = next(
        s["comment"] for s in individual["scores"] if s["quality_id"] == "objectives-observable"
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
