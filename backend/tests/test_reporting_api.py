"""Reporting read models (08-code.md §7, ADR-0006), against Neon.

Averages are checked against numbers computed by hand, so a wrong aggregation cannot pass.
"""

import pytest

RUBRIC = "learnpack-pedagogical-v1"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"
CRITERIA = [
    "objectives-quality",
    "constructive-alignment",
    "instructional-design",
    "inter-lesson-coherence",
    "learning-progression",
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
def content(admin, cleanup, unique):
    body = admin.post(
        "/admin/contents",
        json={
            "generating_system": "LearnpackV1",
            "external_id": f"course-{unique}",
            "consumable_url": COURSE_URL,
            "metadata": {"learningObjectives": ["x"], "targetAudience": "y"},
        },
    ).json()
    cleanup["contents"].append(body["content_id"])
    return body["content_id"]


@pytest.fixture
def campaign(admin, cleanup, content):
    body = admin.post(
        "/admin/campaigns",
        json={
            "rubric_version_id": RUBRIC,
            "required_evaluations_per_content": 2,
            "content_ids": [content],
        },
    ).json()
    cleanup["campaigns"].append(body["campaign_id"])
    return body["campaign_id"]


def assign(admin, campaign_id, content_id, assessor_id) -> str:
    return admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": assessor_id},
    ).json()["assignment_id"]


def find_content(report: dict, content_id: str) -> dict:
    return next(c for c in report["contents"] if c["content_id"] == content_id)


# --------------------------------------------------------------------------- scores


def test_scores_report_averages_across_evaluators(admin, evaluator, content, campaign):
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")

    # Ada gives all 4s except objectives-quality = 2; Bob gives all 4s.
    ada.post(
        "/evaluations",
        json={
            "assignment_id": assign(admin, campaign, content, ada_id),
            "scores": scores(4, **{"objectives-quality": 2}),
        },
    )
    bob.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, bob_id), "scores": scores(4)},
    )

    report = admin.get("/admin/reports/scores").json()
    course = find_content(report, content)

    assert course["evaluator_count"] == 2
    criteria = {c["criterion_id"]: c for c in course["criteria"]}
    # (2 + 4) / 2 = 3.0
    assert criteria["objectives-quality"]["average"] == 3.0
    assert criteria["instructional-design"]["average"] == 4.0
    # 9 scores of 4 plus one of 2 → 38/10
    assert course["average"] == 3.8


def test_dispersion_reflects_the_disagreement(admin, evaluator, content, campaign):
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")

    ada.post(
        "/evaluations",
        json={
            "assignment_id": assign(admin, campaign, content, ada_id),
            "scores": scores(4, **{"objectives-quality": 1}),
        },
    )
    bob.post(
        "/evaluations",
        json={
            "assignment_id": assign(admin, campaign, content, bob_id),
            "scores": scores(4, **{"objectives-quality": 5}),
        },
    )

    report = admin.get("/admin/reports/scores").json()
    criteria = {c["criterion_id"]: c for c in find_content(report, content)["criteria"]}

    contested = criteria["objectives-quality"]["dispersion"]
    assert contested["mean_pairwise_abs_diff"] == 4.0
    assert contested["exact_agreement_pct"] == 0.0
    assert contested["rater_count"] == 2

    agreed = criteria["instructional-design"]["dispersion"]
    assert agreed["exact_agreement_pct"] == 100.0
    assert agreed["stdev"] == 0.0


def test_single_evaluator_has_null_dispersion(admin, evaluator, content, campaign):
    ada, ada_id = evaluator("ada")
    ada.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, ada_id), "scores": scores(4)},
    )

    report = admin.get("/admin/reports/scores").json()
    dispersion = find_content(report, content)["criteria"][0]["dispersion"]
    assert dispersion["stdev"] is None
    assert dispersion["exact_agreement_pct"] is None
    assert dispersion["rater_count"] == 1


def test_comments_and_evaluator_names_reach_the_report(admin, evaluator, content, campaign, unique):
    ada, ada_id = evaluator("ada")
    payload = scores(4)
    payload[0] = {
        "criterion_id": "objectives-quality",
        "score": 2,
        "comment": "verbs are not observable",
    }
    ada.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, ada_id), "scores": payload},
    )

    course = find_content(admin.get("/admin/reports/scores").json(), content)
    individual = course["evaluations"][0]
    assert individual["assessor_name"] == "ada"
    assert individual["superseded"] is False
    comment = next(
        s["comment"] for s in individual["scores"] if s["criterion_id"] == "objectives-quality"
    )
    assert comment == "verbs are not observable"


def test_a_repeated_assessor_does_not_weigh_twice(admin, evaluator, content, campaign, session):
    """ADR-0005 allows repetitions; ADR-0006 says the latest supersedes the earlier one.

    The HTTP guard lives in the assignment, so the repetition is written through the
    repository — exactly the shape an `LLMJudge` would produce `[futuro]`.
    """
    from app.modules.evaluation.domain.evaluation import CriterionScore, Evaluation
    from app.modules.evaluation.infrastructure.repository import SqlAlchemyEvaluationRepository
    from app.shared.domain.ids import new_id

    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")

    # Ada's first pass: all 1s. Bob: all 5s.
    ada.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, ada_id), "scores": scores(1)},
    )
    bob.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, bob_id), "scores": scores(5)},
    )
    # Without collapsing: (1 + 5) / 2 = 3.0
    assert find_content(admin.get("/admin/reports/scores").json(), content)["average"] == 3.0

    # Ada corrects herself: all 3s, submitted later.
    import uuid as _uuid

    correction = Evaluation.submit(
        evaluation_id=new_id(),
        assessor_id=_uuid.UUID(ada_id),
        content_id=_uuid.UUID(content),
        rubric_version_id=RUBRIC,
        scores=[CriterionScore(criterion_id=c, score=3) for c in CRITERIA],
        rubric_criterion_ids=CRITERIA,
        attempt=2,
    )
    SqlAlchemyEvaluationRepository(session).add(correction)
    session.commit()

    course = find_content(admin.get("/admin/reports/scores").json(), content)
    # Ada's 1s are superseded → (3 + 5) / 2 = 4.0, not (1 + 3 + 5) / 3 = 3.0
    assert course["average"] == 4.0
    assert course["evaluator_count"] == 2
    assert len(course["evaluations"]) == 3  # all three stay visible
    assert sum(1 for e in course["evaluations"] if e["superseded"]) == 1


def test_per_evaluator_and_global_averages(admin, evaluator, content, campaign):
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")
    ada.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, ada_id), "scores": scores(2)},
    )
    bob.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, bob_id), "scores": scores(4)},
    )

    report = admin.get("/admin/reports/scores").json()
    averages = {a["assessor_id"]: a for a in report["assessors"]}

    assert averages[ada_id]["average"] == 2.0
    assert averages[ada_id]["display_name"] == "ada"
    assert averages[bob_id]["average"] == 4.0
    assert report["global_average"] == 3.0


def test_content_without_evaluations_reports_null_average(admin, content):
    course = find_content(admin.get("/admin/reports/scores").json(), content)
    assert course["average"] is None
    assert course["evaluator_count"] == 0
    assert course["criteria"] == []


# --------------------------------------------------------------------------- progress


def test_progress_counts_per_evaluator_and_per_course(admin, evaluator, content, campaign, unique):
    ada, ada_id = evaluator("ada")
    bob, bob_id = evaluator("bob")
    carol, carol_id = evaluator("carol")

    ada.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, ada_id), "scores": scores(4)},
    )
    assign(admin, campaign, content, bob_id)  # assigned, never opened
    cancelled = assign(admin, campaign, content, carol_id)
    admin.post(f"/admin/assignments/{cancelled}/cancel")

    report = admin.get("/admin/progress").json()
    by_assessor = {a["assessor_id"]: a["counts"] for a in report["by_assessor"]}

    assert by_assessor[ada_id]["submitted"] == 1
    assert by_assessor[ada_id]["pending"] == 0
    assert by_assessor[bob_id]["assigned"] == 1
    assert by_assessor[bob_id]["pending"] == 1
    assert by_assessor[carol_id]["cancelled"] == 1
    assert by_assessor[carol_id]["pending"] == 0

    course = next(c for c in report["by_content"] if c["content_id"] == content)
    assert course["counts"]["submitted"] == 1
    assert course["counts"]["pending"] == 1
    assert course["counts"]["cancelled"] == 1
    assert course["external_id"] == f"course-{unique}"


def test_reports_require_admin(as_user, cleanup, unique):
    client = as_user(f"user_{unique}", f"{unique}@example.com", "Ada")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    assert client.get("/admin/reports/scores").status_code == 403
    assert client.get("/admin/progress").status_code == 403


def test_scores_report_issues_a_bounded_number_of_queries(admin, evaluator, content, campaign):
    """ADR-0006 requires batch reads: the query count must not grow with the data."""
    ada, ada_id = evaluator("ada")
    ada.post(
        "/evaluations",
        json={"assignment_id": assign(admin, campaign, content, ada_id), "scores": scores(4)},
    )

    from sqlalchemy import event

    from app.platform.db import get_engine

    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", record)
    try:
        assert admin.get("/admin/reports/scores").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", record)

    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    # assessor lookup + contents + metadata schema + evaluations + criterion_scores, plus
    # the auth round-trip. A per-content N+1 would blow well past this.
    assert len(selects) <= 8, "\n".join(selects)
