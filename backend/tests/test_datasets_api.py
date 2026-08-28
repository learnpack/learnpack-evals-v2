"""The admin surface of Datasets: declaring a set, freezing a version, correcting a label
(ADR-0058).

The refusals matter more than the happy path here. A no-op version and a member the registry
never heard of are the two ways a set stops meaning what it says, and both are refused with a
status the console can act on.
"""

import uuid

import pytest
from sqlalchemy import text

COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def course(admin, cleanup, unique):
    """A registered content, minted on demand — datasets are sets of these."""

    def _make(label: str) -> str:
        body = admin.post(
            "/admin/contents",
            json={
                "package_format": "LearnpackV1",
                "external_id": f"course-{label}-{unique}",
                "consumable_url": COURSE_URL,
                "generator_version_id": None,
            },
        ).json()
        cleanup["contents"].append(body["content_id"])
        return str(body["content_id"])

    return _make


@pytest.fixture
def declare(admin, cleanup):
    def _declare(**overrides) -> dict:
        body = {"name": "SME reference set", "note": "the first courses"} | overrides
        response = admin.post("/admin/datasets", json=body)
        assert response.status_code == 201, response.text
        dataset = response.json()
        cleanup["datasets"].append(dataset["dataset_id"])
        return dataset

    return _declare


# --------------------------------------------------------------------------- declaring


def test_declaring_a_dataset_freezes_its_first_version(course, declare):
    first, second = course("a"), course("b")

    dataset = declare(content_ids=[first, second])

    assert dataset["name"] == "SME reference set"
    assert len(dataset["versions"]) == 1
    version = dataset["versions"][0]
    assert version["ordinal"] == 1
    assert version["note"] == "the first courses"
    assert sorted(version["content_ids"]) == sorted([first, second])


def test_a_dataset_needs_at_least_one_course(admin):
    response = admin.post(
        "/admin/datasets", json={"name": "Empty", "note": "nothing", "content_ids": []}
    )
    assert response.status_code == 422


def test_a_member_the_registry_never_heard_of_is_refused_by_name(admin):
    stranger = str(uuid.uuid4())

    response = admin.post(
        "/admin/datasets",
        json={"name": "Wrong", "note": "a typo", "content_ids": [stranger]},
    )

    assert response.status_code == 422
    assert stranger in response.json()["detail"]


def test_declaring_a_dataset_needs_the_admin_role(as_user, cleanup, unique, course):
    client = as_user(f"user_plain_{unique}", f"plain-{unique}@example.com", "Plain")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    assert client.get("/admin/datasets").status_code == 403
    assert (
        client.post(
            "/admin/datasets", json={"name": "N", "note": "n", "content_ids": []}
        ).status_code
        == 403
    )


# --------------------------------------------------------------------------- versions


def test_a_new_membership_becomes_the_next_version(admin, course, declare):
    first, second = course("a"), course("b")
    dataset = declare(content_ids=[first])

    response = admin.post(
        f"/admin/datasets/{dataset['dataset_id']}/versions",
        json={"note": "added the second course", "content_ids": [first, second]},
    )

    assert response.status_code == 201, response.text
    versions = response.json()["versions"]
    assert [v["ordinal"] for v in versions] == [1, 2]
    assert sorted(versions[1]["content_ids"]) == sorted([first, second])


def test_the_same_membership_is_refused_as_a_no_op(admin, course, declare):
    first = course("a")
    dataset = declare(content_ids=[first])

    response = admin.post(
        f"/admin/datasets/{dataset['dataset_id']}/versions",
        json={"note": "saved it again", "content_ids": [first]},
    )

    assert response.status_code == 409
    assert (
        admin.get(f"/admin/datasets/{dataset['dataset_id']}").json()["versions"]
        == (dataset["versions"])
    )


def test_a_version_needs_a_note(admin, course, declare):
    first, second = course("a"), course("b")
    dataset = declare(content_ids=[first])

    response = admin.post(
        f"/admin/datasets/{dataset['dataset_id']}/versions",
        json={"note": "   ", "content_ids": [first, second]},
    )

    assert response.status_code == 422


def test_a_version_of_an_unknown_dataset_is_not_found(admin, course):
    response = admin.post(
        f"/admin/datasets/{uuid.uuid4()}/versions",
        json={"note": "n", "content_ids": [course("a")]},
    )
    assert response.status_code == 404


def test_the_event_says_what_entered_and_what_left(admin, course, declare, session):
    first, second = course("a"), course("b")
    dataset = declare(content_ids=[first])
    admin.post(
        f"/admin/datasets/{dataset['dataset_id']}/versions",
        json={"note": "swapped one course for another", "content_ids": [second]},
    )

    payload = (
        session.execute(
            text(
                "SELECT payload FROM events WHERE aggregate_id = :id "
                "AND event_type = 'DatasetVersionCreated' ORDER BY id DESC LIMIT 1"
            ),
            {"id": dataset["dataset_id"]},
        )
        .scalars()
        .first()
    )

    assert payload["added"] == [second]
    assert payload["removed"] == [first]
    assert payload["ordinal"] == 2


# --------------------------------------------------------------------------- the label


def test_renaming_a_dataset_mints_no_version(admin, course, declare):
    dataset = declare(content_ids=[course("a")])

    response = admin.patch(
        f"/admin/datasets/{dataset['dataset_id']}",
        json={"name": "Reference set — round 2", "description": "the same courses"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Reference set — round 2"
    assert len(response.json()["versions"]) == 1


def test_renaming_an_unknown_dataset_is_not_found(admin):
    response = admin.patch(f"/admin/datasets/{uuid.uuid4()}", json={"name": "Ghost"})
    assert response.status_code == 404


# --------------------------------------------------------------------------- reading


def test_a_dataset_is_listed_and_readable_on_its_own(admin, course, declare):
    dataset = declare(content_ids=[course("a")])

    listing = admin.get("/admin/datasets")
    assert listing.status_code == 200
    assert any(d["dataset_id"] == dataset["dataset_id"] for d in listing.json())

    detail = admin.get(f"/admin/datasets/{dataset['dataset_id']}")
    assert detail.status_code == 200
    assert detail.json() == dataset


def test_an_unknown_dataset_is_not_found(admin):
    assert admin.get(f"/admin/datasets/{uuid.uuid4()}").status_code == 404
