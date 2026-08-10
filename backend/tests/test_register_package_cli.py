"""The local intake loop (ADR-0027): `courses/<name>@<version>/<course>` → one command.

The generator folder is a declaration (ADR-0024): it must name a registered
GeneratorVersion or the literal `unknown`, and the whole tree resolves before anything
registers. The mount preflight is stubbed — no server runs in tests — and COURSES_DIR is
pointed at a throwaway tree so locators mint into the fake mount.
"""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

import app.cli as cli
from app.cli import main, run_register_package, run_register_package_all
from app.config import get_settings
from app.modules.content_profiling.public import ContentProfilingQueries

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"


@pytest.fixture
def courses_tree(tmp_path, monkeypatch, requires_db):
    tree = tmp_path / "courses"
    tree.mkdir()
    monkeypatch.setattr(cli, "COURSES_DIR", tree)
    monkeypatch.setattr(cli, "_mount_preflight", lambda root, course_dir: True)
    return tree


@pytest.fixture
def mount_fetcher(courses_tree, monkeypatch):
    """Resolve the minted mount URLs against the throwaway tree.

    The auto-profiling policy fetches over http by construction (ADR-0029) and no server runs
    in tests. Only the transport is swapped: the registered locators stay genuine http URLs,
    so the locator guard passes on its merits, and only the bytes come from disk. The policy
    instantiates `HttpPackageFetcher()` inside the handler, so patching the module attribute
    takes effect per call.
    """
    from app.config import get_settings
    from app.modules.content_profiling.infrastructure import policies as profiling_policies
    from app.modules.content_profiling.infrastructure.fetchers import FilesystemPackageFetcher

    base = get_settings().local_packages_base_url.rstrip("/") + "/"

    class MountFetcher:
        def __init__(self) -> None:
            self._inner = FilesystemPackageFetcher(courses_tree)

        def fetch(self, locator: str) -> bytes:
            return self._inner.fetch(locator.removeprefix(base))

    monkeypatch.setattr(profiling_policies, "HttpPackageFetcher", MountFetcher)


@pytest.fixture
def generator(register_generator_version, unique):
    """The `courses/<name>@<version>/` convention needs both halves, and since ADR-0031 they
    live in different rows — so the fixture hands back what the folder name is built from."""
    name, version = f"cli-gen-{unique}", "1.0.0"
    return SimpleNamespace(id=register_generator_version(name, version), name=name, version=version)


def put_course(tree: Path, folder: str, slug: str) -> Path:
    """A copy of the frozen bare course under its own slug (the slug is the identity, so
    two courses in one tree must differ)."""
    dest = tree / folder / slug
    shutil.copytree(FIXTURES / "bare-course", dest)
    manifest = json.loads((dest / "learn.json").read_text(encoding="utf-8"))
    manifest["slug"] = slug
    (dest / "learn.json").write_text(json.dumps(manifest), encoding="utf-8")
    return dest


def track(cleanup, session, external_id):
    content_id = session.execute(
        text("SELECT id FROM contents WHERE external_id = :e"), {"e": external_id}
    ).scalar()
    if content_id and content_id not in cleanup["contents"]:
        cleanup["contents"].append(content_id)
    return content_id


def generator_of(session, external_id):
    return session.execute(
        text("SELECT generator_version_id FROM contents WHERE external_id = :e"),
        {"e": external_id},
    ).scalar()


def consumable_url_of(session, external_id):
    return session.execute(
        text("SELECT consumable_url FROM contents WHERE external_id = :e"),
        {"e": external_id},
    ).scalar()


def test_the_tree_registers_with_folder_generators(
    courses_tree, cleanup, unique, session, generator
):
    linked = f"cli-linked-{unique}"
    unknown = f"cli-unknown-{unique}"
    put_course(courses_tree, f"{generator.name}@{generator.version}", linked)
    put_course(courses_tree, "unknown", unknown)

    assert run_register_package_all(courses_tree, "LearnpackV1", "unknown") == 0

    assert track(cleanup, session, linked)
    assert track(cleanup, session, unknown)
    assert generator_of(session, linked) == generator.id
    assert generator_of(session, unknown) is None
    # This is the batch that used to mint mount URLs (ADR-0028): the mount makes the
    # locators fetchable and declares no deployment.
    assert consumable_url_of(session, linked) is None
    assert consumable_url_of(session, unknown) is None


def test_rerunning_the_tree_is_a_noop(courses_tree, cleanup, unique, session, capsys):
    slug = f"cli-rerun-{unique}"
    put_course(courses_tree, "unknown", slug)

    assert run_register_package_all(courses_tree, "LearnpackV1", "unknown") == 0
    assert track(cleanup, session, slug)
    capsys.readouterr()

    assert run_register_package_all(courses_tree, "LearnpackV1", "unknown") == 0
    out = capsys.readouterr().out
    assert "1 created, 0 unchanged" not in out
    assert "0 created, 1 unchanged" in out


def test_an_unregistered_generator_folder_aborts_the_whole_tree(
    courses_tree, cleanup, unique, session, capsys
):
    """A tree-wide declaration deserves a tree-wide check: nothing registers, including
    the courses whose folders were fine."""
    ghost = f"cli-ghost-{unique}"
    fine = f"cli-fine-{unique}"
    put_course(courses_tree, "ghost@9.9.9", ghost)
    put_course(courses_tree, "unknown", fine)

    assert run_register_package_all(courses_tree, "LearnpackV1", "unknown") == 1

    err = capsys.readouterr().err
    assert "names no registered generator" in err
    assert track(cleanup, session, ghost) is None
    assert track(cleanup, session, fine) is None


def test_a_malformed_folder_name_aborts(courses_tree, cleanup, unique, session, capsys):
    slug = f"cli-malformed-{unique}"
    put_course(courses_tree, "not-a-declaration", slug)

    assert run_register_package_all(courses_tree, "LearnpackV1", "unknown") == 1
    assert "not '<name>@<version>' or 'unknown'" in capsys.readouterr().err
    assert track(cleanup, session, slug) is None


def test_single_source_registration(courses_tree, cleanup, unique, session):
    slug = f"cli-single-{unique}"
    course_dir = put_course(courses_tree, "unknown", slug)

    assert (
        run_register_package(
            str(course_dir),
            "unknown",
            "LearnpackV1",
            "unknown",
            "1",
            f"https://{slug}.learn-pack.com/",
        )
        == 0
    )
    assert track(cleanup, session, slug)
    assert generator_of(session, slug) is None
    # `--consumable-url` declares a deployment (ADR-0028); it is the only way a local
    # course gets one, and it is stored verbatim.
    assert consumable_url_of(session, slug) == f"https://{slug}.learn-pack.com/"


def test_a_local_course_registers_without_a_consumable_url(courses_tree, cleanup, unique, session):
    """No declaration, no URL (ADR-0028) — and registration succeeds anyway: the package is
    a complete evaluand for the automated path."""
    slug = f"cli-undeclared-{unique}"
    course_dir = put_course(courses_tree, "unknown", slug)

    assert (
        run_register_package(str(course_dir), "unknown", "LearnpackV1", "unknown", "1", None) == 0
    )
    assert track(cleanup, session, slug)
    assert consumable_url_of(session, slug) is None


def test_a_source_outside_the_tree_is_refused(courses_tree, tmp_path, capsys):
    outside = tmp_path / "elsewhere" / "course"
    shutil.copytree(FIXTURES / "bare-course", outside)

    assert run_register_package(str(outside), "unknown", "LearnpackV1", "unknown", "1", None) == 1
    assert "courses/README.md" in capsys.readouterr().err


def test_the_cli_refuses_silence(capsys):
    """The generator declaration is never defaulted (ADR-0024), and --all owns the tree."""
    assert main(["register-package", "--source", "x"]) == 1
    assert "--generator" in capsys.readouterr().err

    assert main(["register-package", "--all", "--source", "x"]) == 1
    assert "--all" in capsys.readouterr().err


# ------------------------------------------------------- the auto-profiling policy (ADR-0029)


def test_cli_registration_auto_profiles(
    courses_tree, cleanup, unique, session, namespace, accepted_extraction, mount_fetcher, capsys
):
    """The CLI process wires the same policies as the API (ADR-0029 §1): a package registered
    through `register-package --all` is profiled inside its own commit.

    What this proves is the *path* — registering through the CLI entry point ends with a
    profile. It cannot isolate the CLI process: two test modules import `app.main` at module
    scope, so the singleton dispatcher already carries the chain before any test runs. The
    parity claim itself lives in `test_policy_wiring.py`.
    """
    slug = f"cli-autoprofile-{unique}"
    put_course(courses_tree, "unknown", slug)

    assert main(["register-package", "--all"]) == 0

    content_id = track(cleanup, session, slug)
    profile = ContentProfilingQueries(session).get_profile(content_id)
    assert profile is not None
    # Not just "a row exists": an unreachable mount leaves one too, `failed`. A count-only
    # assertion would go green on a broken feature.
    assert profile.status == "ok"
    assert "profiling: 1 profiled" in capsys.readouterr().out


def test_the_batch_reports_that_nothing_was_profiled(
    courses_tree, cleanup, unique, session, capsys
):
    """Without an acceptance the policy declines in silence (ADR-0012); the summary is what
    breaks that silence for the operator."""
    put_course(courses_tree, "unknown", f"cli-quiet-{unique}")

    assert run_register_package_all(courses_tree, "LearnpackV1", "unknown") == 0

    out = capsys.readouterr().out
    assert "profiling: 0 profiled, 0 failed, 1 not profiled" in out
    assert "accept-extraction" in out


# ------------------------------------------------------------------ the mount preflight


def test_the_preflight_probes_a_file_the_course_actually_has(tmp_path, monkeypatch):
    """The check is "does the mount serve this tree", which is true of every format. Probing
    a named manifest tied it to LearnpackV1's convention, so a local course of any other
    format was refused before discovery ever ran — and told to start an API that was already
    running."""
    monkeypatch.setattr(cli, "COURSES_DIR", tmp_path)
    course_dir = tmp_path / "gen@2.0.0" / "a-run"
    (course_dir / "traces").mkdir(parents=True)
    (course_dir / "traces" / "run_metadata.json").write_text("{}", encoding="utf-8")

    probed: list[str] = []

    class RecordingFetcher:
        def fetch(self, locator: str) -> bytes:
            probed.append(locator)
            return b"{}"

    monkeypatch.setattr(cli, "HttpFetcher", RecordingFetcher)

    assert cli._mount_preflight(cli._course_root(course_dir), course_dir)
    assert probed == [
        f"{get_settings().local_packages_base_url.rstrip('/')}"
        "/gen@2.0.0/a-run/traces/run_metadata.json"
    ]
