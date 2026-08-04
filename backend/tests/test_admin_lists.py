"""Admin list endpoints that feed the console (08-code.md §7, prerequisites of block 5).

`GET /admin/campaigns` and `GET /admin/assessors` are read-only surfaces so the admin UI can
populate its campaign list and its assign picker. Both require the admin role.
"""

import pytest

RUBRIC = "learnpack-pedagogical-v1"
COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"


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
            "metadata": {"learningObjectives": ["x"], "targetAudience": "y"},
        },
    ).json()
    cleanup["contents"].append(body["content_id"])
    return body["content_id"]


# --------------------------------------------------------------------------- campaigns


def test_list_campaigns_returns_created_campaigns(admin, cleanup, content, unique):
    created = admin.post(
        "/admin/campaigns",
        json={
            "instrument_version_id": RUBRIC,
            "required_evaluations_per_content": 2,
            "content_ids": [content],
            "metadata_view": ["targetAudience"],
        },
    ).json()
    cleanup["campaigns"].append(created["campaign_id"])

    listing = admin.get("/admin/campaigns")
    assert listing.status_code == 200

    row = next(c for c in listing.json() if c["campaign_id"] == created["campaign_id"])
    assert row["instrument_version_id"] == RUBRIC
    assert row["required_evaluations_per_content"] == 2
    assert row["content_ids"] == [content]
    assert row["metadata_view"] == ["targetAudience"]
    assert row["status"] == "open"


def test_list_campaigns_requires_admin(evaluator):
    client, _ = evaluator("ada")
    assert client.get("/admin/campaigns").status_code == 403


def test_list_campaign_assignments_returns_the_roster(admin, evaluator, cleanup, content):
    campaign = admin.post(
        "/admin/campaigns",
        json={
            "instrument_version_id": RUBRIC,
            "required_evaluations_per_content": 1,
            "content_ids": [content],
        },
    ).json()["campaign_id"]
    cleanup["campaigns"].append(campaign)

    _, ada_id = evaluator("ada")
    created = admin.post(
        f"/admin/campaigns/{campaign}/assignments",
        json={"content_id": content, "assessor_id": ada_id},
    ).json()

    roster = admin.get(f"/admin/campaigns/{campaign}/assignments")
    assert roster.status_code == 200
    rows = roster.json()
    assert len(rows) == 1
    assert rows[0]["assignment_id"] == created["assignment_id"]
    assert rows[0]["assessor_id"] == ada_id
    assert rows[0]["status"] == "assigned"


def test_list_campaign_assignments_unknown_campaign_is_404(admin):
    import uuid

    assert admin.get(f"/admin/campaigns/{uuid.uuid4()}/assignments").status_code == 404


# --------------------------------------------------------------------------- assessors


def test_list_assessors_includes_admins_and_evaluators(admin, evaluator, unique):
    _, ada_id = evaluator("ada")

    listing = admin.get("/admin/assessors")
    assert listing.status_code == 200

    by_id = {a["assessor_id"]: a for a in listing.json()}
    ada = by_id[ada_id]
    assert ada["role"] == "evaluator"
    assert ada["display_name"] == "ada"
    assert ada["email"] == f"ada-{unique}@example.com"

    # The admin who made the request is in the roster too, as an admin.
    admin_id = admin.get("/me").json()["assessor_id"]
    assert by_id[admin_id]["role"] == "admin"


def test_list_assessors_requires_admin(evaluator):
    client, _ = evaluator("ada")
    assert client.get("/admin/assessors").status_code == 403
