"""Content Registry through the API, including the outbox (ADR-0001, ADR-0003, ADR-0005)."""

import pytest
from sqlalchemy import text

COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"


@pytest.fixture
def admin_client(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


def payload(unique: str, **overrides) -> dict:
    body = {
        "package_format": "LearnpackV1",
        "external_id": f"course-{unique}",
        "consumable_url": COURSE_URL,
        "metadata": {
            "learningObjectives": ["Explain prompting"],
            "targetAudience": "Junior developers",
        },
    }
    return body | overrides


def test_register_content_writes_aggregate_and_event(admin_client, cleanup, session, unique):
    response = admin_client.post("/admin/contents", json=payload(unique))
    assert response.status_code == 201, response.text

    body = response.json()
    cleanup["contents"].append(body["content_id"])
    assert body["version"] == "1"
    assert {e["key"] for e in body["metadata"]} == {"learningObjectives", "targetAudience"}
    # valueType comes from the schema, not from the stored row (08-code.md §3).
    types = {e["key"]: e["value_type"] for e in body["metadata"]}
    assert types == {"learningObjectives": "string_list", "targetAudience": "string"}

    # The outbox row committed in the same transaction as the aggregate.
    event_type = session.execute(
        text("SELECT event_type FROM events WHERE aggregate_id = :id"),
        {"id": body["content_id"]},
    ).scalar_one()
    assert event_type == "ContentVersionRegistered"


def test_duplicate_version_is_rejected(admin_client, cleanup, unique):
    first = admin_client.post("/admin/contents", json=payload(unique))
    cleanup["contents"].append(first.json()["content_id"])

    duplicate = admin_client.post("/admin/contents", json=payload(unique))
    assert duplicate.status_code == 409


def test_a_second_version_of_the_same_course_is_allowed(admin_client, cleanup, unique):
    """Content versioning is first class (ADR-0005)."""
    first = admin_client.post("/admin/contents", json=payload(unique))
    cleanup["contents"].append(first.json()["content_id"])

    second = admin_client.post("/admin/contents", json=payload(unique, version="2"))
    assert second.status_code == 201
    cleanup["contents"].append(second.json()["content_id"])
    assert second.json()["content_id"] != first.json()["content_id"]


def test_unknown_metadata_key_is_rejected(admin_client, unique):
    response = admin_client.post(
        "/admin/contents",
        json=payload(unique, metadata={"lessonPlan": "..."}),
    )
    assert response.status_code == 422
    assert any("lessonPlan" in error for error in response.json()["detail"])


def test_missing_required_metadata_is_rejected(admin_client, unique):
    response = admin_client.post(
        "/admin/contents", json=payload(unique, metadata={"targetAudience": "Juniors"})
    )
    assert response.status_code == 422
    assert any("learningObjectives" in error for error in response.json()["detail"])


def test_non_http_url_is_rejected(admin_client, unique):
    response = admin_client.post(
        "/admin/contents", json=payload(unique, consumable_url="ftp://example.com")
    )
    assert response.status_code == 422


def test_unknown_package_format_is_rejected(admin_client, unique):
    response = admin_client.post(
        "/admin/contents", json=payload(unique, package_format="SomeOtherSystem")
    )
    assert response.status_code == 422


def test_update_metadata_writes_aggregate_and_event(admin_client, cleanup, session, unique):
    created = admin_client.post("/admin/contents", json=payload(unique)).json()
    content_id = created["content_id"]
    cleanup["contents"].append(content_id)

    response = admin_client.patch(
        f"/admin/contents/{content_id}/metadata",
        json={
            "metadata": {
                "learningObjectives": ["Explain prompting", "Compare models"],
                "targetAudience": "Senior developers",
                "prerequisites": ["Basic Python"],
            }
        },
    )
    assert response.status_code == 200
    entries = {e["key"]: e["value"] for e in response.json()["metadata"]}
    assert entries["targetAudience"] == "Senior developers"
    assert entries["prerequisites"] == ["Basic Python"]

    event_types = (
        session.execute(
            text("SELECT event_type FROM events WHERE aggregate_id = :id ORDER BY id"),
            {"id": content_id},
        )
        .scalars()
        .all()
    )
    assert event_types == ["ContentVersionRegistered", "ContentMetadataUpdated"]


def test_invalid_metadata_update_leaves_the_content_untouched(admin_client, cleanup, unique):
    created = admin_client.post("/admin/contents", json=payload(unique)).json()
    content_id = created["content_id"]
    cleanup["contents"].append(content_id)

    rejected = admin_client.patch(
        f"/admin/contents/{content_id}/metadata",
        json={"metadata": {"learningObjectives": "not a list", "targetAudience": "Juniors"}},
    )
    assert rejected.status_code == 422

    current = admin_client.get(f"/admin/contents/{content_id}").json()
    entries = {e["key"]: e["value"] for e in current["metadata"]}
    assert entries["learningObjectives"] == ["Explain prompting"]


def test_get_unknown_content_is_404(admin_client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert admin_client.get(f"/admin/contents/{missing}").status_code == 404


def test_list_contents_includes_the_new_one(admin_client, cleanup, unique):
    created = admin_client.post("/admin/contents", json=payload(unique)).json()
    cleanup["contents"].append(created["content_id"])

    listed = admin_client.get("/admin/contents").json()
    assert created["content_id"] in [c["content_id"] for c in listed]
