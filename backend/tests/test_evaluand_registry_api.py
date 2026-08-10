"""Content Registry through the API, including the outbox (ADR-0003, ADR-0005, ADR-0017)."""

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
        # Declared once, here: these tests are about registration, not attribution
        # (ADR-0024). The rule itself is protected by the tests that bypass this helper.
        "generator_version_id": None,
    }
    return body | overrides


def test_register_content_writes_aggregate_and_event(admin_client, cleanup, session, unique):
    response = admin_client.post("/admin/contents", json=payload(unique))
    assert response.status_code == 201, response.text

    body = response.json()
    cleanup["contents"].append(body["content_id"])
    assert body["version"] == "1"
    assert "metadata" not in body  # the declared surface is the package (ADR-0017)

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


def test_non_http_url_is_rejected(admin_client, unique):
    response = admin_client.post(
        "/admin/contents", json=payload(unique, consumable_url="ftp://example.com")
    )
    assert response.status_code == 422


def test_a_content_may_register_without_a_consumable_url(admin_client, cleanup, session, unique):
    """ADR-0028: the key may be absent — no deployed instance is declared. The whole read
    path must carry that null rather than break on it."""
    body = payload(unique)
    del body["consumable_url"]
    response = admin_client.post("/admin/contents", json=body)
    assert response.status_code == 201, response.text

    created = response.json()
    cleanup["contents"].append(created["content_id"])
    assert created["consumable_url"] is None

    listed = admin_client.get("/admin/contents").json()
    row = next(c for c in listed if c["content_id"] == created["content_id"])
    assert row["consumable_url"] is None

    package = admin_client.get(f"/admin/contents/{created['content_id']}/package")
    assert package.status_code == 200, package.text
    assert package.json()["consumable_url"] is None

    stored = session.execute(
        text("SELECT consumable_url FROM contents WHERE id = :id"), {"id": created["content_id"]}
    ).scalar()
    assert stored is None


def test_package_format_is_an_open_vocabulary(admin_client, cleanup, unique):
    # No schema gate anymore (ADR-0017): a new format is data; extraction support for it
    # is an adapter's business, not a registration precondition.
    response = admin_client.post(
        "/admin/contents", json=payload(unique, package_format="SomeOtherSystem")
    )
    assert response.status_code == 201
    cleanup["contents"].append(response.json()["content_id"])


def test_get_unknown_content_is_404(admin_client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert admin_client.get(f"/admin/contents/{missing}").status_code == 404


def test_list_contents_includes_the_new_one(admin_client, cleanup, unique):
    created = admin_client.post("/admin/contents", json=payload(unique)).json()
    cleanup["contents"].append(created["content_id"])

    listed = admin_client.get("/admin/contents").json()
    assert created["content_id"] in [c["content_id"] for c in listed]


# ------------------------------------------------------------ generators & briefs


def mint_generator(admin_client, cleanup, name: str) -> str:
    """The lineage act, tracked for cleanup. Its own helper because it is now a separate call
    that every generator test starts from (ADR-0031 §3)."""
    response = admin_client.post("/admin/generators", json={"name": name})
    assert response.status_code == 201, response.text
    generator_id = response.json()["generator_id"]
    cleanup["generator_lineages"].append(generator_id)
    return generator_id


def add_version(admin_client, cleanup, generator_id: str, version: str, **body) -> dict:
    response = admin_client.post(
        f"/admin/generators/{generator_id}/versions", json={"version": version, **body}
    )
    assert response.status_code == 201, response.text
    created = response.json()
    cleanup["generators"].append(created["generator_version_id"])
    return created


def test_register_generator_version_writes_aggregate_and_event(
    admin_client, cleanup, session, unique
):
    generator_id = mint_generator(admin_client, cleanup, f"gen-{unique}")
    body = add_version(admin_client, cleanup, generator_id, "2.4.0", metadata={"model": "gpt"})
    assert body["metadata"] == {"model": "gpt"}
    # The version answers with its lineage, so a reader never has to join to name it.
    assert body["generator_id"] == generator_id
    assert body["name"] == f"gen-{unique}"

    # The blob comes back on the read path too — it is what the console's Details dialog
    # renders, and the only channel for what a version declares about itself (ADR-0030 §2).
    listed = admin_client.get("/admin/generator-versions").json()
    mine = next(g for g in listed if g["generator_version_id"] == body["generator_version_id"])
    assert mine["metadata"] == {"model": "gpt"}

    event_type = session.execute(
        text("SELECT event_type FROM events WHERE aggregate_id = :id"),
        {"id": body["generator_version_id"]},
    ).scalar_one()
    assert event_type == "GeneratorVersionRegistered"


def test_minting_a_lineage_writes_its_own_event(admin_client, cleanup, session, unique):
    generator_id = mint_generator(admin_client, cleanup, f"gen-{unique}")
    event_type = session.execute(
        text("SELECT event_type FROM events WHERE aggregate_id = :id"),
        {"id": generator_id},
    ).scalar_one()
    assert event_type == "GeneratorRegistered"


def test_duplicate_generator_version_is_rejected(admin_client, cleanup, unique):
    """Immutable identity: a genuinely different generator is a NEW registration."""
    generator_id = mint_generator(admin_client, cleanup, f"gen-{unique}")
    add_version(admin_client, cleanup, generator_id, "1.0")

    duplicate = admin_client.post(
        f"/admin/generators/{generator_id}/versions", json={"version": "1.0"}
    )
    assert duplicate.status_code == 409

    add_version(admin_client, cleanup, generator_id, "1.1")


def test_a_version_under_an_unregistered_generator_is_refused(admin_client):
    """A version never mints its lineage — registering one is the other act, deliberately."""
    response = admin_client.post(
        "/admin/generators/00000000-0000-0000-0000-000000000000/versions",
        json={"version": "1.0"},
    )
    assert response.status_code == 404


def test_the_same_lineage_cannot_be_registered_twice(admin_client, cleanup, unique):
    """Case and surrounding whitespace are not an identity: they are what a keyboard varies
    without meaning to (ADR-0031 §5). Not a near miss — the same lineage, so not overridable."""
    mint_generator(admin_client, cleanup, f"gen-{unique}")

    for variant in (f"gen-{unique}", f"  GEN-{unique.upper()}  "):
        again = admin_client.post("/admin/generators", json={"name": variant})
        assert again.status_code == 409, variant
        # Even an echo cannot force it through: this is not a question being asked.
        forced = admin_client.post(
            "/admin/generators", json={"name": variant, "confirm_distinct_from": f"gen-{unique}"}
        )
        assert forced.status_code == 409, variant


def test_a_near_miss_is_refused_until_the_candidate_is_echoed_back(admin_client, cleanup, unique):
    """The defect this whole change exists for: `gen-alpha` mistyped as `gen-alpah` used to
    mint a second lineage in silence (ADR-0031)."""
    registered = f"gen-alpha-{unique}"
    mint_generator(admin_client, cleanup, registered)

    typo = f"gen-alpah-{unique}"
    refused = admin_client.post("/admin/generators", json={"name": typo})
    assert refused.status_code == 409
    # The refusal names what it thinks you meant, or the operator cannot act on it.
    assert registered in refused.json()["detail"]

    wrong_echo = admin_client.post(
        "/admin/generators", json={"name": typo, "confirm_distinct_from": "something-else"}
    )
    assert wrong_echo.status_code == 409

    confirmed = admin_client.post(
        "/admin/generators", json={"name": typo, "confirm_distinct_from": registered}
    )
    assert confirmed.status_code == 201, confirmed.text
    cleanup["generator_lineages"].append(confirmed.json()["generator_id"])


def test_a_blank_generator_name_is_rejected(admin_client):
    assert admin_client.post("/admin/generators", json={"name": "   "}).status_code == 422


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


def test_generator_artifact_endpoints_are_gone(admin_client):
    """ADR-0030: the generator's internals are not held here. The route is retired, not
    merely unused — a client still calling it must find out."""
    assert (
        admin_client.post(
            "/admin/generators/00000000-0000-0000-0000-000000000000/artifacts",
            json={"kind": "prompt-template", "locator": "https://example.com/t"},
        ).status_code
        == 404
    )
    assert (
        admin_client.get(
            "/admin/generators/00000000-0000-0000-0000-000000000000/artifacts"
        ).status_code
        == 404
    )


def test_generators_and_briefs_are_listed(admin_client, cleanup, unique):
    generator_id = mint_generator(admin_client, cleanup, f"gen-{unique}")
    version_id = add_version(admin_client, cleanup, generator_id, "1.0")["generator_version_id"]
    brief_id = admin_client.post("/admin/briefs", json={"brief": f"brief-{unique}"}).json()[
        "brief_id"
    ]
    cleanup["briefs"].append(brief_id)

    # Two resources since ADR-0031 §3: /generators lists lineages, /generator-versions the
    # versions under them. One path cannot mean both.
    generators = admin_client.get("/admin/generators").json()
    versions = admin_client.get("/admin/generator-versions").json()
    briefs = admin_client.get("/admin/briefs").json()
    assert generator_id in {g["generator_id"] for g in generators}
    assert version_id in {v["generator_version_id"] for v in versions}
    assert brief_id in {b["brief_id"] for b in briefs}


# ------------------------------------------------- content package & provenance


def test_content_carries_package_brief_generator_and_provenance(
    admin_client, cleanup, session, unique
):
    lineage_id = mint_generator(admin_client, cleanup, f"gen-{unique}")
    generator_id = add_version(admin_client, cleanup, lineage_id, "1.0")["generator_version_id"]
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


def test_registration_may_declare_an_unknown_generator(admin_client, cleanup, unique):
    """No package, no brief, and a generator explicitly declared unknown (ADR-0024):
    a legitimate registration — a human-written baseline has no generator."""
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


def test_registration_without_the_generator_key_is_rejected(admin_client, unique):
    """The rule itself, bypassing `payload()`: silence is not a declaration (ADR-0024)."""
    silent = {
        "package_format": "LearnpackV1",
        "external_id": f"course-{unique}",
        "consumable_url": COURSE_URL,
    }

    response = admin_client.post("/admin/contents", json=silent)

    assert response.status_code == 422
    assert "generator_version_id" in response.text


def test_a_discovered_generator_can_be_attributed_through_the_api(
    admin_client, cleanup, unique, session
):
    lineage_id = mint_generator(admin_client, cleanup, f"late-gen-{unique}")
    generator = add_version(admin_client, cleanup, lineage_id, "1.0.0")
    content = admin_client.post("/admin/contents", json=payload(unique)).json()
    cleanup["contents"].append(content["content_id"])
    assert content["generator_version_id"] is None

    response = admin_client.post(
        f"/admin/contents/{content['content_id']}/generator",
        json={"generator_version_id": generator["generator_version_id"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["generator_version_id"] == generator["generator_version_id"]
    # The provenance of a discovery, so it stays distinguishable from a declaration.
    assert body["generator_attributed_by"] is not None
    assert body["generator_attributed_at"] is not None

    # Attributing again is refused: the act fills a void, it does not revise.
    again = admin_client.post(
        f"/admin/contents/{content['content_id']}/generator",
        json={"generator_version_id": generator["generator_version_id"]},
    )
    assert again.status_code == 409


def test_attribution_rejects_a_ghost_generator_and_a_ghost_content(admin_client, cleanup, unique):
    ghost = "00000000-0000-0000-0000-000000000000"
    content = admin_client.post("/admin/contents", json=payload(unique)).json()
    cleanup["contents"].append(content["content_id"])

    assert (
        admin_client.post(
            f"/admin/contents/{content['content_id']}/generator",
            json={"generator_version_id": ghost},
        ).status_code
        == 422
    )
    assert (
        admin_client.post(
            f"/admin/contents/{ghost}/generator", json={"generator_version_id": ghost}
        ).status_code
        == 404
    )


def test_the_command_cannot_be_built_without_a_declaration():
    """The second of the two gates ADR-0024 names — the application command, guarded
    independently of the request model above."""
    from app.modules.evaluand_registry.application.register_content_version import (
        RegisterContentVersionCommand,
    )

    with pytest.raises(TypeError):
        RegisterContentVersionCommand(  # type: ignore[call-arg]
            package_format="LearnpackV1",
            external_id="silent-course",
            consumable_url=COURSE_URL,
        )


# ------------------------------------------------------------ register by source (ADR-0027)


@pytest.fixture
def course_server(tmp_path):
    """A live copy of the frozen bare course, served over real http on an ephemeral port —
    the endpoint's discovery, hashing and consumable_url all ride the actual transport.
    The files stay writable, so a test can mutate the course between registrations."""
    import functools
    import http.server
    import pathlib
    import shutil
    import threading

    fixtures = pathlib.Path(__file__).parent / "fixtures" / "learnpack_v1"
    course_dir = tmp_path / "bare-course"
    shutil.copytree(fixtures / "bare-course", course_dir)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # keep 404 probes out of the test output
            pass

    handler = functools.partial(QuietHandler, directory=str(tmp_path))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", course_dir
    server.shutdown()


def source_payload(base_url: str, **overrides) -> dict:
    return {
        "package_format": "LearnpackV1",
        "source_locator": f"{base_url}/bare-course",
        "generator_version_id": None,
    } | overrides


def test_register_by_source_discovers_the_package(admin_client, cleanup, session, course_server):
    base_url, _ = course_server
    response = admin_client.post(
        "/admin/contents/register-by-source", json=source_payload(base_url)
    )
    assert response.status_code == 201, response.text

    body = response.json()
    cleanup["contents"].append(body["content"]["content_id"])
    assert body["created"] is True
    assert body["artifact_count"] == 5  # manifests + two lesson bodies + one exercise file
    assert body["content"]["external_id"] == "bare-course"  # identity from the package
    assert body["content"]["consumable_url"] == f"{base_url}/bare-course"

    artifacts = session.execute(
        text("SELECT count(*) FROM content_package_artifacts WHERE content_id = :id"),
        {"id": body["content"]["content_id"]},
    ).scalar()
    assert artifacts == 5
    content_hash = session.execute(
        text("SELECT content_hash FROM contents WHERE id = :id"),
        {"id": body["content"]["content_id"]},
    ).scalar()
    assert content_hash


def test_reregistering_an_unchanged_source_is_a_noop(admin_client, cleanup, course_server):
    base_url, _ = course_server
    first = admin_client.post("/admin/contents/register-by-source", json=source_payload(base_url))
    cleanup["contents"].append(first.json()["content"]["content_id"])

    second = admin_client.post("/admin/contents/register-by-source", json=source_payload(base_url))
    assert second.status_code == 200, second.text
    assert second.json()["created"] is False
    assert second.json()["content"]["content_id"] == first.json()["content"]["content_id"]


def test_changed_content_under_the_same_version_is_a_conflict(admin_client, cleanup, course_server):
    base_url, course_dir = course_server
    first = admin_client.post("/admin/contents/register-by-source", json=source_payload(base_url))
    cleanup["contents"].append(first.json()["content"]["content_id"])

    readme = course_dir / "exercises" / "00-frontmatter-only" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\ndrifted", encoding="utf-8")

    conflict = admin_client.post(
        "/admin/contents/register-by-source", json=source_payload(base_url)
    )
    assert conflict.status_code == 409
    assert "declare a new version" in conflict.json()["detail"]


def test_an_undiscoverable_source_is_rejected_not_registered(admin_client, session, course_server):
    base_url, _ = course_server
    response = admin_client.post(
        "/admin/contents/register-by-source",
        json=source_payload(base_url, source_locator=f"{base_url}/no-such-course"),
    )
    assert response.status_code == 422

    orphan = session.execute(
        text("SELECT count(*) FROM contents WHERE consumable_url = :url"),
        {"url": f"{base_url}/no-such-course"},
    ).scalar()
    assert orphan == 0


def test_a_non_http_source_is_refused(admin_client):
    response = admin_client.post(
        "/admin/contents/register-by-source",
        json=source_payload("http://x", source_locator="C:/courses/bare-course"),
    )
    assert response.status_code == 422
    assert "CLI" in response.json()["detail"]


def test_register_by_source_without_the_generator_key_is_rejected(admin_client, course_server):
    base_url, _ = course_server
    body = source_payload(base_url)
    del body["generator_version_id"]  # silence is not a declaration (ADR-0024)

    assert admin_client.post("/admin/contents/register-by-source", json=body).status_code == 422


def test_the_supported_formats_are_listed(admin_client):
    response = admin_client.get("/admin/contents/formats")
    assert response.status_code == 200
    assert response.json() == ["LearnpackV1"]
