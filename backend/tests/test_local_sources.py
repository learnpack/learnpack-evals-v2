"""Declared local source roots: what is readable, and where it is served (ADR-0035).

No database, no app, no network. Two things are pinned here: a malformed declaration never
becomes a running configuration, and a path an operator typed never escapes its root.
"""

import pytest
from pydantic import ValidationError

from app import cli
from app.config import Settings, get_settings, parse_source_roots
from app.modules.evaluand_registry.infrastructure import local_sources
from app.modules.evaluand_registry.infrastructure.local_sources import LocalSourceError

LOCAL_DB = "postgresql+psycopg://postgres:postgres@localhost:15434/learnpack_evals_dev"


@pytest.fixture
def declare(monkeypatch):
    """Declare `LOCAL_SOURCE_ROOTS` as the environment would. Settings are read per call,
    so the cache is what has to be cleared — the pattern of test_auth_local.py."""

    def declared(value: str) -> None:
        monkeypatch.setenv("LOCAL_SOURCE_ROOTS", value)
        get_settings.cache_clear()

    yield declared
    get_settings.cache_clear()


# --------------------------------------------------------------------- the declaration


def test_entries_parse_in_order_and_split_on_the_first_equals():
    """A Windows path carries its own colon and, with a drive-relative form, its own
    equals-free ambiguity; splitting on the first separator is what keeps it whole."""
    assert parse_source_roots("runs=D:\\gen\\out, batch-2 = /srv/courses ") == [
        ("runs", "D:\\gen\\out"),
        ("batch-2", "/srv/courses"),
    ]
    assert parse_source_roots("") == []
    assert parse_source_roots(" , ") == []


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("runs", "not '<key>=<path>'"),
        ("runs=", "not '<key>=<path>'"),
        ("=/srv/courses", "not '<key>=<path>'"),
        ("Runs=/srv/courses", "must match"),
        ("my runs=/srv/courses", "must match"),
        ("runs/old=/srv/courses", "must match"),
        ("courses=/srv/courses", "built-in local source root"),
        ("runs=/a,runs=/b", "declared twice"),
    ],
)
def test_a_malformed_declaration_refuses_to_boot_in_local_mode(raw, message):
    """ADR-0035 §2: nobody can act on these, and a key names a URL prefix."""
    with pytest.raises(ValidationError, match=message):
        Settings(auth_mode="local", database_url=LOCAL_DB, local_source_roots=raw)


def test_the_same_declaration_is_inert_under_clerk_mode():
    """A leftover variable must never break a deploy that does not read it."""
    Settings(auth_mode="clerk", local_source_roots="courses=/srv, courses=/srv, oops")


# ------------------------------------------------------------------------- the roots


def test_the_builtin_root_comes_first_and_keeps_its_url(declare):
    """Locators registered before ADR-0035 point at `/packages` and are never rewritten."""
    declare("runs=/srv/runs")

    builtin = local_sources.configured_roots()[0]

    assert (builtin.key, builtin.builtin) == ("courses", True)
    assert builtin.path == local_sources.COURSES_DIR
    assert builtin.url_base == get_settings().local_packages_base_url.rstrip("/")
    assert builtin.mount_path == "/packages"


def test_a_declared_root_is_served_under_its_own_disjoint_prefix(declare):
    """Disjoint from `/packages`, so no key can shadow a folder inside courses/ and no
    mount depends on registration order."""
    declare("runs=/srv/runs")

    runs = local_sources.root_for("runs")

    assert runs is not None and not runs.builtin
    assert runs.url_base == f"{get_settings().local_sources_base_url.rstrip('/')}/runs"
    assert runs.mount_path == "/sources/runs"
    assert not runs.mount_path.startswith(local_sources.BUILTIN_MOUNT_PATH)
    assert local_sources.root_for("nope") is None


def test_a_root_whose_directory_is_missing_is_reported_and_skipped(declare, tmp_path):
    """An environment fact, not a declaration error: it must not stop the app booting."""
    present = tmp_path / "present"
    present.mkdir()
    declare(f"present={present}, gone={tmp_path / 'gone'}")

    keys = {root.key: root.exists for root in local_sources.configured_roots()}
    mounted = {root.key for root in local_sources.mounts()}

    assert keys["present"] is True and keys["gone"] is False
    assert "present" in mounted and "gone" not in mounted


# -------------------------------------------------------------------- the containment


@pytest.fixture
def root(tmp_path, declare):
    tree = tmp_path / "runs"
    (tree / "batch" / "course").mkdir(parents=True)
    declare(f"runs={tree}")
    resolved = local_sources.root_for("runs")
    assert resolved is not None
    return resolved


@pytest.mark.parametrize("relative", ["..", "../..", "batch/../../elsewhere", "/etc"])
def test_a_path_outside_the_root_is_refused(root, relative):
    with pytest.raises(LocalSourceError):
        local_sources.resolve(root, relative)


def test_a_symlink_out_of_the_root_is_refused(root, tmp_path):
    """Resolved before the check, which also matches what the mount will serve: StaticFiles
    refuses to follow a symlink out of its directory."""
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root.path / "escape").symlink_to(outside, target_is_directory=True)
    except OSError:  # pragma: no cover - Windows without developer mode
        pytest.skip("creating a symlink needs privileges this machine does not grant")

    with pytest.raises(LocalSourceError):
        local_sources.resolve(root, "escape")


def test_a_file_is_not_a_folder_to_scan(root):
    (root.path / "notes.txt").write_text("x", encoding="utf-8")

    with pytest.raises(LocalSourceError):
        local_sources.resolve(root, "notes.txt")


def test_the_root_itself_and_its_subfolders_resolve(root):
    assert local_sources.resolve(root, "") == root.path.resolve()
    assert local_sources.resolve(root, "batch/course") == (root.path / "batch" / "course").resolve()
    # Operator input, so a leading separator is a typo rather than an escape.
    assert local_sources.resolve(root, "/batch") == (root.path / "batch").resolve()


# ------------------------------------------------------------------------- the locators


def test_a_package_under_a_declared_root_registers_locators_into_its_mount(root):
    package = local_sources.package_root(root, "batch/course")

    assert package.locator_for("learn.json") == f"{root.url_base}/batch/course/learn.json"
    # ADR-0028: serving a package's bytes is not deploying a course.
    assert package.consumable_url is None


def test_the_builtin_root_mints_the_locator_the_cli_has_always_minted(declare):
    """Anti-drift. The CLI keeps its own `courses/`-only resolution (it is its whole
    contract); what may never diverge is the locator both write into a permanent row."""
    declare("")
    relative = "learnpack-generator@1.0.0/my-course"

    from_cli = cli._course_root(cli.COURSES_DIR / "learnpack-generator@1.0.0" / "my-course")
    from_module = local_sources.locator_base(local_sources.builtin_root(), relative)

    assert cli.COURSES_DIR == local_sources.COURSES_DIR
    assert from_cli.locator_for("learn.json") == f"{from_module}/learn.json"
