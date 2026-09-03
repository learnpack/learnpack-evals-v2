"""The validity of a claim against a campaign, end to end (ADR-0063).

What is under test is the **crossing**: that the human side is scoped to the campaign the way
ADR-0060 §1 scopes it, that the automated side is narrowed to the pinned pair, and that a
claim with no human item is listed rather than hidden. The arithmetic itself is checked
against fakes in `test_claim_validity.py`.

The automated half is inserted directly rather than produced by running an assessor: the
pipeline that produces judgments has its own tests, and building one here would test it twice
while making this file about something else.
"""

import json
import uuid as _uuid

import pytest
from conftest import open_campaign_over
from sqlalchemy import text

from app.platform.db import SessionLocal

RUBRIC = "learnpack-pedagogical-2.0.0"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"

# Three claims: two over qualities the reference instrument elicits, one over a quality it
# does not — which is the case ADR-0063 §6 insists on listing.
ELICITED_A = "objectives-observable"
ELICITED_B = "coherence-reinforcement"
NOT_ELICITED = "instruction-application"

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
    return [{"quality_id": q, "score": overrides.get(q, value), "comment": None} for q in QUALITIES]


# --------------------------------------------------------------------------- fixtures


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
def instrument(requires_db, unique):
    """A published instrument version with three claims, and its teardown.

    `cleanup` has no bucket for instruments the suite invents, so this fixture owns it.
    """
    version_id = f"validity-under-test-{unique}"
    with SessionLocal() as session:
        session.execute(
            text(
                """
                INSERT INTO instrument_versions
                    (id, instrument_id, version, name, purpose, status, quality_dimensions)
                VALUES (:id, 'validity-under-test', :version, 'Validity under test', 'a test',
                        'published', :dims)
                """
            ),
            {
                "id": version_id,
                # `{instrument_id}-{version}` is an invariant of the aggregate (08-code §9).
                "version": unique,
                "dims": json.dumps(
                    {
                        ELICITED_A: "objectives-quality",
                        ELICITED_B: "inter-lesson-coherence",
                        NOT_ELICITED: "instructional-design",
                    }
                ),
            },
        )
        for ord_, (claim_id, quality) in enumerate(
            [
                ("cl-elicited-a", ELICITED_A),
                ("cl-elicited-b", ELICITED_B),
                ("cl-not-elicited", NOT_ELICITED),
            ]
        ):
            session.execute(
                text(
                    """
                    INSERT INTO instrument_claims
                        (instrument_version_id, claim_id, ord, statement, quality_ids,
                         warrants, alternative_explanations, sufficiency)
                    VALUES (:v, :c, :ord, :statement, :qualities,
                            '["Biggs"]'::jsonb, '["the adapter read the wrong field"]'::jsonb,
                            '{"rule": "conjunctive"}'::jsonb)
                    """
                ),
                {
                    "v": version_id,
                    "c": claim_id,
                    "ord": ord_,
                    "statement": f"The course does {claim_id}.",
                    "qualities": json.dumps([quality]),
                },
            )
        session.commit()

    yield version_id

    with SessionLocal() as session:
        session.execute(text("DELETE FROM instrument_versions WHERE id = :id"), {"id": version_id})
        session.commit()


@pytest.fixture
def robot(requires_db, cleanup, unique, instrument):
    """An automated assessor, the way `assessors` stores one (ADR-0016)."""
    assessor_id = str(_uuid.uuid4())
    with SessionLocal() as session:
        session.execute(
            text(
                """
                INSERT INTO assessors (id, role, kind, source_config, display_name)
                VALUES (:id, 'evaluator', 'automated', :config, :name)
                """
            ),
            {
                "id": assessor_id,
                "config": json.dumps(
                    {
                        "name": f"robot-{unique}",
                        "version": "1",
                        # An automated assessor is owed to an instrument (ADR-0016, ADR-0019).
                        "instrumentId": "validity-under-test",
                    }
                ),
                "name": f"robot-{unique}:1",
            },
        )
        session.commit()
    cleanup["assessors"].append(assessor_id)
    return assessor_id


@pytest.fixture
def judge(requires_db, instrument, robot):
    """Record what the assessor concluded about one course, without running it."""

    def _judge(content_id: str, **status_by_claim: str) -> None:
        evaluation_id = str(_uuid.uuid4())
        judgment_id = str(_uuid.uuid4())
        with SessionLocal() as session:
            session.execute(
                text(
                    """
                    INSERT INTO evaluations
                        (id, assessor_id, content_id, instrument_version_id, submitted_at)
                    VALUES (:id, :assessor, :content, :instrument, now())
                    """
                ),
                {
                    "id": evaluation_id,
                    "assessor": robot,
                    "content": content_id,
                    "instrument": instrument,
                },
            )
            session.execute(
                text(
                    """
                    INSERT INTO quality_judgments
                        (id, evaluation_id, content_id, instrument_version_id, coverage)
                    VALUES (:id, :evaluation, :content, :instrument, '{}'::jsonb)
                    """
                ),
                {
                    "id": judgment_id,
                    "evaluation": evaluation_id,
                    "content": content_id,
                    "instrument": instrument,
                },
            )
            for claim_id, claim_status in status_by_claim.items():
                session.execute(
                    text(
                        """
                        INSERT INTO judgment_claims
                            (judgment_id, claim_id, status, evidence_basis)
                        VALUES (:j, :c, :s, '{}'::jsonb)
                        """
                    ),
                    {"j": judgment_id, "c": claim_id.replace("_", "-"), "s": claim_status},
                )
            session.commit()

    return _judge


# --------------------------------------------------------------------------- helpers


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


def validity_of(admin, campaign_id, assessor_id, instrument_version_id):
    return admin.get(
        f"/admin/validity?campaign={campaign_id}&assessor={assessor_id}"
        f"&instrument={instrument_version_id}"
    )


def claim(body: dict, claim_id: str) -> dict:
    return next(c for c in body["claims"] if c["claim_id"] == claim_id)


# --------------------------------------------------------------------------- tests


def test_a_claim_whose_quality_nobody_was_asked_is_listed_not_hidden(
    admin, evaluator, make_content, instrument, robot, judge, cleanup
):
    """ADR-0063 §6: hiding it would look like an instrument that never asked (ADR-0011 §3)."""
    content = make_content("course")
    campaign = open_campaign_over(
        admin,
        cleanup,
        [content],
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    ada, ada_id = evaluator("ada")
    submit(ada, admin, campaign, content, ada_id)
    judge(content, cl_elicited_a="supported", cl_not_elicited="supported")

    body = validity_of(admin, campaign, robot, instrument).json()

    assert [c["claim_id"] for c in body["claims"]] == [
        "cl-elicited-a",
        "cl-elicited-b",
        "cl-not-elicited",
    ]
    absent = claim(body, "cl-not-elicited")
    assert absent["status"] == "unvalidated"
    assert absent["reason"] == "no_reference_item"


def test_the_sample_is_the_courses_both_sides_judged(
    admin, evaluator, make_content, instrument, robot, judge, cleanup
):
    judged, unjudged = make_content("judged"), make_content("unjudged")
    campaign = open_campaign_over(
        admin,
        cleanup,
        [judged, unjudged],
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    ada, ada_id = evaluator("ada")
    submit(ada, admin, campaign, judged, ada_id)
    submit(ada, admin, campaign, unjudged, ada_id)
    judge(judged, cl_elicited_a="supported")

    body = validity_of(admin, campaign, robot, instrument).json()

    assert body["courses_in_campaign"] == 2
    assert body["courses_judged"] == 1


def test_a_course_the_panel_did_not_commit_on_is_grey_and_out_of_the_table(
    admin, evaluator, make_content, instrument, robot, judge, cleanup
):
    """A mean of 3 is the panel declining, and it is counted rather than dropped in silence."""
    content = make_content("course")
    campaign = open_campaign_over(
        admin,
        cleanup,
        [content],
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    ada, ada_id = evaluator("ada")
    submit(ada, admin, campaign, content, ada_id, **{ELICITED_A: 3})
    judge(content, cl_elicited_a="supported")

    row = claim(validity_of(admin, campaign, robot, instrument).json(), "cl-elicited-a")

    assert row["grey"] == 1
    assert row["sample"] == 0


def test_the_numbers_carry_their_denominators_and_never_a_bare_zero(
    admin, evaluator, make_content, instrument, robot, judge, cleanup
):
    content = make_content("course")
    campaign = open_campaign_over(
        admin,
        cleanup,
        [content],
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    ada, ada_id = evaluator("ada")
    submit(ada, admin, campaign, content, ada_id, **{ELICITED_A: 5})
    judge(content, cl_elicited_a="supported")

    row = claim(validity_of(admin, campaign, robot, instrument).json(), "cl-elicited-a")

    assert row["sensitivity"] == {"hit": 1, "of": 1}
    # The experts never rejected, so there is no specificity to state — and `0 %` would say
    # the assessor missed everything (ADR-0063 §3).
    assert row["specificity"] == {"hit": 0, "of": 0}
    assert row["kappa"] is None
    assert row["status"] == "unvalidated"


def test_another_assessors_judgments_are_not_read(
    admin, evaluator, make_content, instrument, robot, judge, cleanup, unique
):
    """The pair is the point: a judgment by somebody else says nothing about this one."""
    content = make_content("course")
    campaign = open_campaign_over(
        admin,
        cleanup,
        [content],
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    ada, ada_id = evaluator("ada")
    submit(ada, admin, campaign, content, ada_id)
    judge(content, cl_elicited_a="supported")

    stranger = str(_uuid.uuid4())
    with SessionLocal() as session:
        session.execute(
            text(
                "INSERT INTO assessors (id, role, kind, source_config) "
                "VALUES (:id, 'evaluator', 'automated', :c)"
            ),
            {
                "id": stranger,
                "c": json.dumps(
                    {
                        "name": f"other-{unique}",
                        "version": "1",
                        "instrumentId": "validity-under-test",
                    }
                ),
            },
        )
        session.commit()
    cleanup["assessors"].append(stranger)

    body = validity_of(admin, campaign, stranger, instrument).json()

    assert body["courses_judged"] == 0
    assert claim(body, "cl-elicited-a")["sample"] == 0


def test_an_unknown_coordinate_is_a_404_that_says_which(
    admin, evaluator, make_content, instrument, robot, cleanup
):
    content = make_content("course")
    campaign = open_campaign_over(
        admin,
        cleanup,
        [content],
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]

    missing_campaign = validity_of(admin, str(_uuid.uuid4()), robot, instrument)
    assert missing_campaign.status_code == 404
    assert "campaign" in missing_campaign.json()["detail"]

    missing_assessor = validity_of(admin, campaign, str(_uuid.uuid4()), instrument)
    assert missing_assessor.status_code == 404
    assert "assessor" in missing_assessor.json()["detail"]

    missing_instrument = validity_of(admin, campaign, robot, "no-such-instrument")
    assert missing_instrument.status_code == 404
    assert "instrument" in missing_instrument.json()["detail"]


def test_an_evaluator_may_not_read_it(evaluator, admin, make_content, instrument, robot, cleanup):
    content = make_content("course")
    campaign = open_campaign_over(
        admin,
        cleanup,
        [content],
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=1,
    )["campaign_id"]
    ada, _ = evaluator("ada")

    assert validity_of(ada, campaign, robot, instrument).status_code == 403
