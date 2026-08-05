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


# Requiredness stays a schema capability (unit-tested in test_metadata_schema.py), but the
# seeded LearnpackV1 schema requires nothing: forcing metadata at registration forces a
# human to type the declared surface the instrument evaluates.


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


# ------------------------------------------------------------ generators & briefs


def test_register_generator_writes_aggregate_and_event(admin_client, cleanup, session, unique):
    response = admin_client.post(
        "/admin/generators",
        json={"name": f"gen-{unique}", "version": "2.4.0", "metadata": {"model": "gpt"}},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    cleanup["generators"].append(body["generator_version_id"])
    assert body["metadata"] == {"model": "gpt"}

    event_type = session.execute(
        text("SELECT event_type FROM events WHERE aggregate_id = :id"),
        {"id": body["generator_version_id"]},
    ).scalar_one()
    assert event_type == "GeneratorVersionRegistered"


def test_duplicate_generator_identity_is_rejected(admin_client, cleanup, unique):
    """Immutable identity: a genuinely different generator is a NEW registration."""
    first = admin_client.post("/admin/generators", json={"name": f"gen-{unique}", "version": "1.0"})
    cleanup["generators"].append(first.json()["generator_version_id"])

    duplicate = admin_client.post(
        "/admin/generators", json={"name": f"gen-{unique}", "version": "1.0"}
    )
    assert duplicate.status_code == 409

    new_version = admin_client.post(
        "/admin/generators", json={"name": f"gen-{unique}", "version": "1.1"}
    )
    assert new_version.status_code == 201
    cleanup["generators"].append(new_version.json()["generator_version_id"])


def test_register_brief_writes_aggregate_and_event(admin_client, cleanup, session, unique):
    response = admin_client.post(
        "/admin/briefs",
        json={"brief": f"an intro course on loops ({unique})", "fields": {"level": "intro"}},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    cleanup["briefs"].append(body["brief_id"])

    event_type = session.execute(
        text("SELECT event_type FROM events WHERE aggregate_id = :id"),
        {"id": body["brief_id"]},
    ).scalar_one()
    assert event_type == "BriefRegistered"


def test_blank_brief_is_rejected(admin_client):
    assert admin_client.post("/admin/briefs", json={"brief": "   "}).status_code == 422


def test_generator_artifact_requires_a_registered_generator(admin_client):
    response = admin_client.post(
        "/admin/generators/00000000-0000-0000-0000-000000000000/artifacts",
        json={"kind": "prompt-template", "locator": "https://example.com/t"},
    )
    assert response.status_code == 404


def test_generator_artifacts_are_registered_and_listed(admin_client, cleanup, unique):
    generator_id = admin_client.post(
        "/admin/generators", json={"name": f"gen-{unique}", "version": "1.0"}
    ).json()["generator_version_id"]
    cleanup["generators"].append(generator_id)

    created = admin_client.post(
        f"/admin/generators/{generator_id}/artifacts",
        json={"kind": "knowledge-graph", "locator": "https://example.com/kg.json"},
    )
    assert created.status_code == 201, created.text

    listed = admin_client.get(f"/admin/generators/{generator_id}/artifacts").json()
    assert [(a["kind"], a["locator"]) for a in listed] == [
        ("knowledge-graph", "https://example.com/kg.json")
    ]


def test_generators_and_briefs_are_listed(admin_client, cleanup, unique):
    generator_id = admin_client.post(
        "/admin/generators", json={"name": f"gen-{unique}", "version": "1.0"}
    ).json()["generator_version_id"]
    cleanup["generators"].append(generator_id)
    brief_id = admin_client.post("/admin/briefs", json={"brief": f"brief-{unique}"}).json()[
        "brief_id"
    ]
    cleanup["briefs"].append(brief_id)

    generators = admin_client.get("/admin/generators").json()
    briefs = admin_client.get("/admin/briefs").json()
    assert generator_id in {g["generator_version_id"] for g in generators}
    assert brief_id in {b["brief_id"] for b in briefs}


# ------------------------------------------------- content package & provenance


def test_content_carries_package_brief_generator_and_provenance(
    admin_client, cleanup, session, unique
):
    generator_id = admin_client.post(
        "/admin/generators", json={"name": f"gen-{unique}", "version": "1.0"}
    ).json()["generator_version_id"]
    cleanup["generators"].append(generator_id)
    brief_id = admin_client.post("/admin/briefs", json={"brief": f"brief-{unique}"}).json()[
        "brief_id"
    ]
    cleanup["briefs"].append(brief_id)

    response = admin_client.post(
        "/admin/contents",
        json=payload(
            unique,
            artifacts=[
                {"kind": "manifest", "locator": "https://x/learn.json", "format": "json"},
                {"kind": "item-bank", "locator": "https://x/items.json"},
            ],
            brief_id=brief_id,
            generator_version_id=generator_id,
            edit_provenance="pure",
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    cleanup["contents"].append(body["content_id"])
    assert body["brief_id"] == brief_id
    assert body["edit_provenance"] == "pure"

    package = admin_client.get(f"/admin/contents/{body['content_id']}/package").json()
    assert [(a["kind"], a["format"]) for a in package["artifacts"]] == [
        ("manifest", "json"),
        ("item-bank", None),
    ]

    event_payload = session.execute(
        text("SELECT payload FROM events WHERE aggregate_id = :id"),
        {"id": body["content_id"]},
    ).scalar_one()
    assert event_payload["briefId"] == brief_id
    assert event_payload["generatorVersionId"] == generator_id
    assert event_payload["editProvenance"] == "pure"


def test_unknown_brief_or_generator_is_rejected(admin_client, unique):
    ghost = "00000000-0000-0000-0000-000000000000"
    assert (
        admin_client.post("/admin/contents", json=payload(unique, brief_id=ghost)).status_code
        == 422
    )
    assert (
        admin_client.post(
            "/admin/contents", json=payload(unique, generator_version_id=ghost)
        ).status_code
        == 422
    )


def test_registration_without_evaluand_fields_still_works(admin_client, cleanup, unique):
    """The legacy manual path: no package, no brief, no generator — provenance unknown."""
    response = admin_client.post("/admin/contents", json=payload(unique))
    assert response.status_code == 201
    body = response.json()
    cleanup["contents"].append(body["content_id"])
    assert body["brief_id"] is None
    assert body["generator_version_id"] is None
    assert body["edit_provenance"] == "unknown"

    package = admin_client.get(f"/admin/contents/{body['content_id']}/package").json()
    assert package["artifacts"] == []
    assert package["consumable_url"] == COURSE_URL
