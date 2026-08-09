"""The local intake loop (ADR-0027): `courses/<name>@<version>/<course>` → one command.

The generator folder is a declaration (ADR-0024): it must name a registered
GeneratorVersion or the literal `unknown`, and the whole tree resolves before anything
registers. The mount preflight is stubbed — no server runs in tests — and COURSES_DIR is
pointed at a throwaway tree so locators mint into the fake mount.
"""

import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import text

import app.cli as cli
from app.cli import main, run_register_package, run_register_package_all
from app.modules.evaluand_registry.application.register_generator_version import (
    RegisterGeneratorVersion,
    RegisterGeneratorVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork

FIXTURES = Path(__file__).parent / "fixtures" / "learnpack_v1"


@pytest.fixture
def courses_tree(tmp_path, monkeypatch, requires_db):
    tree = tmp_path / "courses"
    tree.mkdir()
    monkeypatch.setattr(cli, "COURSES_DIR", tree)
    monkeypatch.setattr(cli, "_mount_preflight", lambda root: True)
    return tree


@pytest.fixture
def generator(cleanup, unique):
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        version = RegisterGeneratorVersion(
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )(RegisterGeneratorVersionCommand(name=f"cli-gen-{unique}", version="1.0.0"))
    cleanup["generators"].append(version.id)
    return version


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
