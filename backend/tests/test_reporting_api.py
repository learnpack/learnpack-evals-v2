"""The cross-campaign workload report (ADR-0006, ADR-0060 §6), against Neon.

Who evaluated what, across campaigns — the one question Reporting still answers without a
campaign. What a course scored is read inside its campaign; see `test_campaign_report.py`.
"""

import pytest
from conftest import open_campaign_over

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
def content(admin, cleanup, unique):
    body = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"course-{unique}",
            "consumable_url": COURSE_URL,
            "generator_version_id": None,
            "metadata": {"learningObjectives": ["x"], "targetAudience": "y"},
        },
    ).json()
    cleanup["contents"].append(body["content_id"])
    return body["content_id"]


@pytest.fixture
def campaign(admin, cleanup, content):
    return open_campaign_over(
        admin,
        cleanup,
        [content],
        name="Reporting campaign",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=2,
    )["campaign_id"]


def assign(admin, campaign_id, content_id, assessor_id) -> str:
    return admin.post(
        f"/admin/campaigns/{campaign_id}/assignments",
        json={"content_id": content_id, "assessor_id": assessor_id},
    ).json()["assignment_id"]


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


def test_the_workload_report_requires_admin(as_user, cleanup, unique):
    client = as_user(f"user_{unique}", f"{unique}@example.com", "Ada")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    assert client.get("/admin/progress").status_code == 403


def test_there_is_no_cross_campaign_scores_report(admin):
    """Retired by ADR-0060 §6: a score has no meaning outside the campaign that fixed the
    instrument, and a filtered version would be a second way to ask the same question."""
    assert admin.get("/admin/reports/scores").status_code == 404
