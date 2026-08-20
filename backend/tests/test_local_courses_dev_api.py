"""The dev intake surface: browse a declared root, preview, register (ADR-0035).

Two properties carry most of the weight here. The endpoints do not exist outside local mode
— 404 before 401, so the gate cannot be probed — and the preview tells the truth about what
registering would do, including the case where it would do nothing.

No server runs in tests, so `HttpFetcher` is swapped for one that resolves the minted mount
URLs off disk: the locators stay genuine http URLs (the guards pass on their merits), only
the transport changes. Same trick as test_register_package_cli.py's `mount_fetcher`.
"""

import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.modules.content_profiling.public import ContentProfilingQueries
from app.modules.evaluand_registry.infrastructure import dev_router, local_sources
from app.shared.infrastructure.fetchers import FetchError, FilesystemFetcher

V1_FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"
V2_FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v2"
V2_RUN = "03-html-fundamentals-20260810191731"

ENDPOINTS = [
    ("get", "/dev/local-courses/roots", None),
    ("get", "/dev/local-courses/browse?root=courses", None),
    ("post", "/dev/local-courses/scan", {"root": "courses", "package_format": "LearnpackV1"}),
    (
        "post",
        "/dev/local-courses/register",
        {
            "root": "courses",
            "path": "x",
            "package_format": "LearnpackV1",
            "generator_version_id": None,
        },
    ),
]


@pytest.fixture
def local_auth(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def clerk_auth(monkeypatch):
    """Force the default mode. Not redundant: clearing the cache re-reads the developer's
    `.env`, which says `AUTH_MODE=local` — the setting has to be overridden, not forgotten."""
    monkeypatch.setenv("AUTH_MODE", "clerk")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def runs_root(tmp_path, monkeypatch, requires_db):
    """One declared root, empty, plus a `courses/` tree that is not the repo's."""
    monkeypatch.setattr(local_sources, "COURSES_DIR", tmp_path / "courses")
    (tmp_path / "courses").mkdir()
    tree = tmp_path / "runs"
    tree.mkdir()
    monkeypatch.setenv("LOCAL_SOURCE_ROOTS", f"runs={tree}")
    get_settings.cache_clear()
    yield tree
    get_settings.cache_clear()


@pytest.fixture
def served(monkeypatch):
    """Serve the declared roots off disk, as the real mounts serve them over http."""
    calls: list[str] = []

    class MountFetcher:
        def __init__(self, timeout_seconds: float = 10.0) -> None:
            pass

        def fetch(self, locator: str) -> bytes:
            calls.append(locator)
            for root in local_sources.configured_roots():
                base = f"{root.url_base}/"
                if locator.startswith(base):
                    return FilesystemFetcher(root.path).fetch(locator.removeprefix(base))
            raise FetchError(f"nothing serves '{locator}'")

    monkeypatch.setattr(dev_router, "HttpFetcher", MountFetcher)
    return calls


@pytest.fixture
def admin_client(as_user, cleanup, promote, unique, local_auth):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


def put_v1_course(tree: Path, folder: str, slug: str) -> Path:
    """A copy of the frozen bare course under its own slug — the slug is the identity."""
    destination = tree / folder / slug
    shutil.copytree(V1_FIXTURES / "bare-course", destination)
    manifest = json.loads((destination / "learn.json").read_text(encoding="utf-8"))
    manifest["slug"] = slug
    (destination / "learn.json").write_text(json.dumps(manifest), encoding="utf-8")
    return destination


def change_bytes(course: Path) -> None:
    readme = next(course.rglob("*.md"), None)
    assert readme is not None
    readme.write_text(readme.read_text(encoding="utf-8") + "\n\nregenerated\n", encoding="utf-8")


def scan(client, root="runs", path="batch", package_format="LearnpackV1", version="1"):
    response = client.post(
        "/dev/local-courses/scan",
        json={"root": root, "path": path, "package_format": package_format, "version": version},
    )
    assert response.status_code == 200, response.text
    return response.json()


def register(client, path, generator_version_id=None, root="runs", version="1", **extra):
    return client.post(
        "/dev/local-courses/register",
        json={
            "root": root,
            "path": path,
            "package_format": extra.get("package_format", "LearnpackV1"),
            "version": version,
            "generator_version_id": generator_version_id,
        },
    )


def by_name(payload: dict, name: str) -> dict:
    return next(candidate for candidate in payload["candidates"] if candidate["name"] == name)


def track(cleanup, session, external_id):
    content_id = session.execute(
        text("SELECT id FROM contents WHERE external_id = :e"), {"e": external_id}
    ).scalar()
    if content_id and content_id not in cleanup["contents"]:
        cleanup["contents"].append(content_id)
    return content_id


# --------------------------------------------------------------------------- the gates


@pytest.mark.parametrize(("method", "url", "body"), ENDPOINTS)
def test_the_surface_does_not_exist_outside_local_mode(requires_db, clerk_auth, method, url, body):
    """404 and not 401, with no credentials at all: the gate is declared on the router, so
    it resolves before the identity — otherwise every path would confirm its own existence
    to anyone who asked. No identity override here on purpose; a 401 would be a real one."""
    from fastapi.testclient import TestClient

    from app.main import app

    response = getattr(TestClient(app), method)(url, **({"json": body} if body else {}))

    assert response.status_code == 404, response.text


@pytest.mark.parametrize(("method", "url", "body"), ENDPOINTS)
def test_an_evaluator_cannot_register_anything(
    as_user, cleanup, unique, local_auth, runs_root, method, url, body
):
    client = as_user(f"user_eval_{unique}", f"eval-{unique}@example.com", "Eval")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    response = getattr(client, method)(url, **({"json": body} if body else {}))

    assert response.status_code == 403, response.text


# ---------------------------------------------------------------------- roots + browse


def test_the_roots_are_listed_with_the_builtin_first(admin_client, runs_root):
    roots = admin_client.get("/dev/local-courses/roots").json()

    assert [root["key"] for root in roots] == ["courses", "runs"]
    assert roots[0]["builtin"] is True and roots[0]["exists"] is True
    assert roots[1]["url_base"].endswith("/sources/runs")


def test_browsing_shows_how_many_folders_each_folder_holds(admin_client, runs_root):
    """So "you are one level too high" is visible before a scan reads anything."""
    put_v1_course(runs_root, "batch", "a-course")
    put_v1_course(runs_root, "batch", "b-course")
    (runs_root / "empty").mkdir()

    top = admin_client.get("/dev/local-courses/browse?root=runs").json()

    assert top["parent"] is None
    assert {(e["name"], e["child_dir_count"]) for e in top["entries"]} == {
        ("batch", 2),
        ("empty", 0),
    }
    inside = admin_client.get("/dev/local-courses/browse?root=runs&path=batch").json()
    assert [e["path"] for e in inside["entries"]] == ["batch/a-course", "batch/b-course"]
    assert inside["parent"] == ""


def test_browsing_refuses_what_is_not_inside_a_root(admin_client, runs_root):
    assert admin_client.get("/dev/local-courses/browse?root=nope").status_code == 404
    assert admin_client.get("/dev/local-courses/browse?root=runs&path=..").status_code == 422


# ----------------------------------------------------------------------- the verdicts


def test_a_folder_nobody_has_registered_scans_as_new(admin_client, runs_root, served, unique):
    put_v1_course(runs_root, "batch", f"dev-new-{unique}")

    candidate = scan(admin_client)["candidates"][0]

    assert candidate["verdict"] == "new"
    assert candidate["external_id"] == f"dev-new-{unique}"
    assert candidate["artifact_count"] > 0
    assert candidate["existing"] is None


def test_registering_turns_the_same_folder_unchanged(
    admin_client, runs_root, served, cleanup, session, unique
):
    slug = f"dev-unchanged-{unique}"
    put_v1_course(runs_root, "batch", slug)
    assert register(admin_client, f"batch/{slug}").status_code == 201
    track(cleanup, session, slug)

    candidate = by_name(scan(admin_client), slug)

    assert candidate["verdict"] == "unchanged"
    assert candidate["existing"]["version"] == "1"
    # Registered with `unknown`, so the one repair that exists is offered (ADR-0024).
    assert candidate["can_attribute_generator"] is True


def test_changed_bytes_under_the_declared_version_scan_as_a_conflict(
    admin_client, runs_root, served, cleanup, session, unique
):
    slug = f"dev-conflict-{unique}"
    course = put_v1_course(runs_root, "batch", slug)
    assert register(admin_client, f"batch/{slug}").status_code == 201
    track(cleanup, session, slug)
    change_bytes(course)

    candidate = by_name(scan(admin_client), slug)

    assert candidate["verdict"] == "conflict"
    assert candidate["existing"]["has_hash"] is True


def test_changed_bytes_with_the_declared_version_free_scan_as_a_new_version(
    admin_client, runs_root, served, cleanup, session, unique
):
    """The verdict that would be invisible if `new` covered it: the course is known, these
    bytes are not, and registering succeeds."""
    slug = f"dev-newversion-{unique}"
    course = put_v1_course(runs_root, "batch", slug)
    assert register(admin_client, f"batch/{slug}").status_code == 201
    track(cleanup, session, slug)
    change_bytes(course)

    candidate = by_name(scan(admin_client, version="2"), slug)

    assert candidate["verdict"] == "new_version"
    assert candidate["existing"]["version"] == "1"
    assert register(admin_client, f"batch/{slug}", version="2").status_code == 201


def test_a_folder_that_is_not_a_package_does_not_poison_its_siblings(
    admin_client, runs_root, served, unique
):
    put_v1_course(runs_root, "batch", f"dev-sibling-{unique}")
    (runs_root / "batch" / "not-a-course").mkdir()

    candidates = scan(admin_client)["candidates"]

    broken = by_name({"candidates": candidates}, "not-a-course")
    assert broken["verdict"] == "unreadable"
    assert "learn.json" in broken["error"]
    assert by_name({"candidates": candidates}, f"dev-sibling-{unique}")["verdict"] == "new"


def test_an_unknown_format_is_refused_before_anything_is_read(admin_client, runs_root, served):
    response = admin_client.post(
        "/dev/local-courses/scan",
        json={"root": "runs", "path": "", "package_format": "Nonsense", "version": "1"},
    )

    assert response.status_code == 422
    assert served == []


def test_the_mount_is_probed_once_per_scan(admin_client, runs_root, served, unique):
    """One statement about the tree, not one per folder — every readable folder in it is
    served the same way."""
    put_v1_course(runs_root, "batch", f"dev-probe-a-{unique}")
    put_v1_course(runs_root, "batch", f"dev-probe-b-{unique}")

    payload = scan(admin_client)

    assert payload["mount_ok"] is True
    assert len(served) == 1
    assert served[0].startswith(local_sources.root_for("runs").url_base)


# --------------------------------------------------------------------- the registration


def test_registering_declares_a_generator_and_no_deployment(
    admin_client, runs_root, served, cleanup, session, unique, register_generator_version
):
    generator_version_id = register_generator_version(f"dev-gen-{unique}", "2.0.0")
    slug = f"dev-registered-{unique}"
    put_v1_course(runs_root, "batch", slug)

    response = register(admin_client, f"batch/{slug}", str(generator_version_id))

    assert response.status_code == 201, response.text
    body = response.json()
    cleanup["contents"].append(body["content"]["content_id"])
    assert body["created"] is True and body["artifact_count"] > 0
    assert body["content"]["generator_version_id"] == str(generator_version_id)
    # ADR-0028: a served root is not a deployment.
    assert body["content"]["consumable_url"] is None
    assert body["can_attribute_generator"] is False
    locators = session.execute(
        text("SELECT locator FROM content_package_artifacts WHERE content_id = :c"),
        {"c": body["content"]["content_id"]},
    ).scalars()
    assert all(locator.startswith(local_sources.root_for("runs").url_base) for locator in locators)


def test_re_registering_unchanged_content_discards_the_generator_it_declared(
    admin_client, runs_root, served, cleanup, session, unique, register_generator_version
):
    """The trap this surface has to be honest about (ADR-0035 §9): the hash match returns the
    existing row untouched, so the generator just declared is silently dropped. Attribution
    is its own act, never a side effect of re-scanning."""
    generator_version_id = register_generator_version(f"dev-late-{unique}", "3.0.0")
    slug = f"dev-late-{unique}"
    put_v1_course(runs_root, "batch", slug)
    assert register(admin_client, f"batch/{slug}").status_code == 201
    content_id = track(cleanup, session, slug)

    response = register(admin_client, f"batch/{slug}", str(generator_version_id))

    assert response.status_code == 200, response.text
    assert response.json()["created"] is False
    assert response.json()["can_attribute_generator"] is True
    session.commit()  # see what the request wrote, not this session's snapshot
    assert (
        session.execute(
            text("SELECT generator_version_id FROM contents WHERE id = :c"), {"c": content_id}
        ).scalar()
        is None
    )


def test_an_unregistered_generator_version_is_refused(
    admin_client, runs_root, served, unique, session
):
    slug = f"dev-nogen-{unique}"
    put_v1_course(runs_root, "batch", slug)

    response = register(admin_client, f"batch/{slug}", "00000000-0000-0000-0000-000000000000")

    assert response.status_code == 422, response.text
    assert track({"contents": []}, session, slug) is None


def test_changed_content_under_the_same_version_is_refused(
    admin_client, runs_root, served, cleanup, session, unique
):
    slug = f"dev-changed-{unique}"
    course = put_v1_course(runs_root, "batch", slug)
    assert register(admin_client, f"batch/{slug}").status_code == 201
    track(cleanup, session, slug)
    change_bytes(course)

    response = register(admin_client, f"batch/{slug}")

    assert response.status_code == 409
    assert "declare a new version" in response.json()["detail"]


def test_registering_is_refused_when_the_mount_does_not_serve_the_tree(
    admin_client, runs_root, monkeypatch, session, unique
):
    """Binding, not advisory: the locators about to be written are permanent, and a client
    guard is one the server cannot rely on."""

    class DeadMount:
        def __init__(self, timeout_seconds: float = 10.0) -> None:
            pass

        def fetch(self, locator: str) -> bytes:
            raise FetchError("connection refused")

    monkeypatch.setattr(dev_router, "HttpFetcher", DeadMount)
    slug = f"dev-nomount-{unique}"
    put_v1_course(runs_root, "batch", slug)

    response = register(admin_client, f"batch/{slug}")

    assert response.status_code == 422
    assert "does not serve this tree" in response.json()["detail"]
    assert track({"contents": []}, session, slug) is None


def test_a_registered_local_course_is_auto_profiled(
    admin_client,
    runs_root,
    served,
    cleanup,
    session,
    unique,
    namespace,
    accepted_extraction,
    monkeypatch,
):
    """Parity with the CLI path, and the reason a registration is slow: the profiling policy
    runs inside the request because the locators are http (ADR-0029)."""
    from app.modules.content_profiling.infrastructure import policies as profiling_policies
    from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher

    base = f"{local_sources.root_for('runs').url_base}/"

    class MountFetcher:
        def __init__(self) -> None:
            self._inner = FilesystemPackageFetcher(runs_root)

        def fetch(self, locator: str) -> bytes:
            return self._inner.fetch(locator.removeprefix(base))

        def fetch_all(self, locators):
            return {locator: self.fetch(locator) for locator in locators}

    monkeypatch.setattr(profiling_policies, "HttpPackageFetcher", MountFetcher)
    slug = f"dev-profiled-{unique}"
    put_v1_course(runs_root, "batch", slug)

    assert register(admin_client, f"batch/{slug}").status_code == 201
    content_id = track(cleanup, session, slug)
    profile = ContentProfilingQueries(session).get_profile(content_id)

    assert profile is not None
    # Not just "a row exists": an unreachable mount leaves a `failed` one too.
    assert profile.status == "ok"


def test_a_v2_run_tree_registers_through_the_same_endpoints(
    admin_client, runs_root, served, cleanup, session
):
    """Nothing here is V1-shaped: the format is a declaration and discovery dispatches on it."""
    shutil.copytree(V2_FIXTURES / V2_RUN, runs_root / "batch" / V2_RUN)

    payload = scan(admin_client, package_format="LearnpackV2")
    assert payload["candidates"][0]["verdict"] == "new"

    response = register(admin_client, f"batch/{V2_RUN}", package_format="LearnpackV2")

    assert response.status_code == 201, response.text
    cleanup["contents"].append(response.json()["content"]["content_id"])
    assert response.json()["content"]["package_format"] == "LearnpackV2"
