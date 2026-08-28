"""Admin list endpoints that feed the console (08-code.md §7, prerequisites of block 5).

`GET /admin/campaigns` and `GET /admin/assessors` are read-only surfaces so the admin UI can
populate its campaign list and its assign picker. Both require the admin role.
"""

import uuid

import pytest
from conftest import declare_dataset_over, open_campaign_over

RUBRIC = "learnpack-pedagogical-2.0.0"
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
            "generator_version_id": None,
        },
    ).json()
    cleanup["contents"].append(body["content_id"])
    return body["content_id"]


# --------------------------------------------------------------------------- campaigns


def test_list_campaigns_returns_created_campaigns(admin, cleanup, content, unique):
    created = open_campaign_over(
        admin,
        cleanup,
        [content],
        name="Campaign in the admin list",
        instrument_version_id=RUBRIC,
        required_evaluations_per_content=2,
    )

    listing = admin.get("/admin/campaigns")
    assert listing.status_code == 200

    row = next(c for c in listing.json() if c["campaign_id"] == created["campaign_id"])
    assert row["name"] == "Campaign in the admin list"
    assert row["description"] is None
    assert row["instrument_version_id"] == RUBRIC
    assert row["required_evaluations_per_content"] == 2
    assert row["content_ids"] == [content]
    assert row["status"] == "open"


def test_list_campaigns_requires_admin(evaluator):
    client, _ = evaluator("ada")
    assert client.get("/admin/campaigns").status_code == 403


# --------------------------------------------------------------------- renaming (ADR-0055)


@pytest.fixture
def campaign(admin, cleanup, content):
    """An open campaign, named at birth."""
    return open_campaign_over(
        admin,
        cleanup,
        [content],
        name="First round",
        description="The courses of the first round",
        instrument_version_id=RUBRIC,
    )["campaign_id"]


def test_a_campaign_is_named_when_it_opens(admin, campaign):
    row = next(c for c in admin.get("/admin/campaigns").json() if c["campaign_id"] == campaign)
    assert row["name"] == "First round"
    assert row["description"] == "The courses of the first round"


def test_a_campaign_cannot_open_without_a_name(admin, content, cleanup):
    response = admin.post(
        "/admin/campaigns",
        json={
            "name": "   ",
            "instrument_version_id": RUBRIC,
            "required_evaluations_per_content": 1,
            "dataset_version_id": declare_dataset_over(admin, cleanup, [content]),
        },
    )
    assert response.status_code == 422


def test_renaming_replaces_the_label_and_survives_the_round_trip(admin, campaign):
    renamed = admin.patch(f"/admin/campaigns/{campaign}", json={"name": "Second round"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Second round"
    # The description is not carried over: the label is replaced whole (ADR-0055 §4).
    assert renamed.json()["description"] is None

    row = next(c for c in admin.get("/admin/campaigns").json() if c["campaign_id"] == campaign)
    assert row["name"] == "Second round"
    assert row["description"] is None


def test_renaming_refuses_a_blank_name(admin, campaign):
    assert admin.patch(f"/admin/campaigns/{campaign}", json={"name": "  "}).status_code == 422


def test_renaming_an_unknown_campaign_is_404(admin):
    response = admin.patch(f"/admin/campaigns/{uuid.uuid4()}", json={"name": "Nowhere"})
    assert response.status_code == 404


def test_renaming_requires_admin(evaluator, campaign):
    client, _ = evaluator("ada")
    assert client.patch(f"/admin/campaigns/{campaign}", json={"name": "Mine"}).status_code == 403


def test_a_closed_campaign_still_renames(admin, campaign):
    """The decision, at the edge: a label binds nothing, so closing does not protect it."""
    assert admin.post(f"/admin/campaigns/{campaign}/close").status_code == 200

    renamed = admin.patch(f"/admin/campaigns/{campaign}", json={"name": "Closed and renamed"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Closed and renamed"
    assert renamed.json()["status"] == "closed"


def test_list_campaign_assignments_returns_the_roster(admin, evaluator, cleanup, content):
    campaign = open_campaign_over(
        admin,
        cleanup,
        [content],
        name="Campaign with a roster",
        instrument_version_id=RUBRIC,
    )["campaign_id"]

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
    assert ada["kind"] == "human"
    assert ada["automated"] is None

    # The admin who made the request is in the roster too, as an admin.
    admin_id = admin.get("/me").json()["assessor_id"]
    assert by_id[admin_id]["role"] == "admin"


def test_list_assessors_names_the_automated_kind(admin, cleanup, session, unique):
    """The two kinds are structurally different (ADR-0016): a list that mixes them has to
    say which is which, and an automated one carries its artifact identity."""
    from app.modules.identity.application.register_automated_assessor import (
        RegisterAutomatedAssessor,
        RegisterAutomatedAssessorCommand,
    )
    from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository

    name, lineage = f"structural-{unique}", f"qa-copy-{unique}"
    registered = RegisterAutomatedAssessor(SqlAlchemyAssessorRepository(session))(
        RegisterAutomatedAssessorCommand(
            name=name,
            version="1",
            display_name=f"Structural {unique}",
            source_config={"name": name, "version": "1", "instrumentId": lineage},
        )
    )
    session.commit()
    assessor_id = str(registered.assessor.assessor_id)
    cleanup["assessors"].append(assessor_id)

    row = next(a for a in admin.get("/admin/assessors").json() if a["assessor_id"] == assessor_id)
    assert row["kind"] == "automated"
    assert row["automated"] == {"name": name, "version": "1", "instrument_id": lineage}
    # No external credential, and the role it is created with says nothing about it.
    assert row["email"] is None


def test_list_assessors_requires_admin(evaluator):
    client, _ = evaluator("ada")
    assert client.get("/admin/assessors").status_code == 403


# ------------------------------------------------- the scope comes from a set (ADR-0058)


def test_a_campaign_takes_its_scope_from_the_version_it_names(admin, cleanup, content, unique):
    """The version is *how* the scope was chosen; the copy is *what* was judged (§5)."""
    version_id = declare_dataset_over(admin, cleanup, [content], f"scope-{unique}")

    campaign = admin.post(
        "/admin/campaigns",
        json={
            "name": "Campaign over a named set",
            "instrument_version_id": RUBRIC,
            "required_evaluations_per_content": 1,
            "dataset_version_id": version_id,
        },
    )

    assert campaign.status_code == 201, campaign.text
    body = campaign.json()
    cleanup["campaigns"].append(body["campaign_id"])
    assert body["dataset_version_id"] == version_id
    assert body["content_ids"] == [content]


def test_a_campaign_naming_a_version_nobody_declared_is_refused(admin):
    response = admin.post(
        "/admin/campaigns",
        json={
            "name": "Campaign over nothing",
            "instrument_version_id": RUBRIC,
            "required_evaluations_per_content": 1,
            "dataset_version_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 422
    assert "dataset version" in response.json()["detail"]


def test_the_campaign_keeps_the_courses_the_version_had_when_it_opened(
    admin, cleanup, content, unique
):
    """A later version of the same set does not move a campaign that already opened."""
    second = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"course-later-{unique}",
            "consumable_url": COURSE_URL,
            "generator_version_id": None,
        },
    ).json()["content_id"]
    cleanup["contents"].append(second)

    campaign = open_campaign_over(
        admin, cleanup, [content], name=f"Frozen scope {unique}", instrument_version_id=RUBRIC
    )
    dataset_id = next(
        d["dataset_id"]
        for d in admin.get("/admin/datasets").json()
        if any(v["version_id"] == campaign["dataset_version_id"] for v in d["versions"])
    )
    admin.post(
        f"/admin/datasets/{dataset_id}/versions",
        json={"note": "added one after the campaign opened", "content_ids": [content, second]},
    )

    row = next(
        c
        for c in admin.get("/admin/campaigns").json()
        if c["campaign_id"] == campaign["campaign_id"]
    )
    assert row["content_ids"] == [content]
    assert row["dataset_version_id"] == campaign["dataset_version_id"]
