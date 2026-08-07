"""Bulk registration through the CLI — both payload shapes (ADR-0024).

The declaration of the generator comes from whoever owns the shape: the canonical file
carries it per entry, LearnPack's raw shape does not, so `--generator` declares it for the
whole file. There is no fallback between them, which is what these tests pin down.
"""

import json

import pytest
from sqlalchemy import text

from app.cli import main, run_import_learnpack
from app.modules.evaluand_registry.application.register_generator_version import (
    RegisterGeneratorVersion,
    RegisterGeneratorVersionCommand,
)
from app.modules.evaluand_registry.infrastructure.repository import (
    SqlAlchemyGeneratorVersionRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork

COURSE_URL = "https://introduction-to-generative-ai.learn-pack.com/"


@pytest.fixture
def generator(cleanup, unique):
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        version = RegisterGeneratorVersion(
            generators=SqlAlchemyGeneratorVersionRepository(session),
            publisher=uow.events,
            uow=uow,
        )(RegisterGeneratorVersionCommand(name=f"import-gen-{unique}", version="1.0.0"))
    cleanup["generators"].append(version.id)
    return version.id


def write(tmp_path, courses):
    path = tmp_path / "courses.json"
    path.write_text(json.dumps(courses), encoding="utf-8")
    return path


def track(cleanup, session, external_id):
    content_id = session.execute(
        text("SELECT id FROM contents WHERE external_id = :e"), {"e": external_id}
    ).scalar()
    if content_id:
        cleanup["contents"].append(content_id)
    return content_id


def generator_of(session, external_id):
    return session.execute(
        text("SELECT generator_version_id FROM contents WHERE external_id = :e"),
        {"e": external_id},
    ).scalar()


# ------------------------------------------------------------------ canonical shape


def test_canonical_entries_declare_their_own_generator(
    cleanup, unique, session, tmp_path, generator
):
    external_id = f"canonical-{unique}"
    path = write(
        tmp_path,
        [
            {
                "package_format": "LearnpackV1",
                "external_id": external_id,
                "consumable_url": COURSE_URL,
                "generator_version_id": str(generator),
            }
        ],
    )

    assert run_import_learnpack(path, use_acl=False) == 0
    assert track(cleanup, session, external_id)
    assert generator_of(session, external_id) == generator


def test_a_canonical_entry_without_the_key_is_invalid(cleanup, unique, session, tmp_path):
    """Silence is not a declaration: the row is counted invalid, not registered."""
    external_id = f"silent-{unique}"
    path = write(
        tmp_path,
        [
            {
                "package_format": "LearnpackV1",
                "external_id": external_id,
                "consumable_url": COURSE_URL,
            }
        ],
    )

    assert run_import_learnpack(path, use_acl=False) == 1
    assert track(cleanup, session, external_id) is None


def test_a_canonical_entry_may_declare_unknown(cleanup, unique, session, tmp_path):
    external_id = f"canonical-unknown-{unique}"
    path = write(
        tmp_path,
        [
            {
                "package_format": "LearnpackV1",
                "external_id": external_id,
                "consumable_url": COURSE_URL,
                "generator_version_id": None,
            }
        ],
    )

    assert run_import_learnpack(path, use_acl=False) == 0
    assert track(cleanup, session, external_id)
    assert generator_of(session, external_id) is None


# ------------------------------------------------------------------ ACL shape


def test_the_acl_file_takes_its_declaration_from_the_flag(
    cleanup, unique, session, tmp_path, generator
):
    slug = f"acl-{unique}"
    path = write(tmp_path, [{"slug": slug, "url": COURSE_URL}])

    assert run_import_learnpack(path, use_acl=True, generator=str(generator)) == 0
    assert track(cleanup, session, slug)
    assert generator_of(session, slug) == generator


def test_the_acl_file_may_declare_unknown(cleanup, unique, session, tmp_path):
    slug = f"acl-unknown-{unique}"
    path = write(tmp_path, [{"slug": slug, "url": COURSE_URL}])

    assert run_import_learnpack(path, use_acl=True, generator="unknown") == 0
    assert track(cleanup, session, slug)
    assert generator_of(session, slug) is None


def test_an_unregistered_generator_fails_before_the_loop(cleanup, unique, session, tmp_path):
    """A file-wide declaration deserves a file-wide check: nothing is registered."""
    slug = f"acl-ghost-{unique}"
    path = write(tmp_path, [{"slug": slug, "url": COURSE_URL}])

    ghost = "00000000-0000-0000-0000-000000000000"
    assert run_import_learnpack(path, use_acl=True, generator=ghost) == 1
    assert track(cleanup, session, slug) is None


# ------------------------------------------------------------------ the two paths refuse each other


def test_acl_without_the_flag_is_refused(tmp_path, capsys):
    path = write(tmp_path, [{"slug": "x", "url": COURSE_URL}])

    assert main(["import-learnpack", "--file", str(path), "--acl"]) == 1
    assert "--generator" in capsys.readouterr().err


def test_the_flag_without_acl_is_refused(tmp_path, capsys):
    path = write(tmp_path, [])

    assert main(["import-learnpack", "--file", str(path), "--generator", "unknown"]) == 1
    assert "per entry" in capsys.readouterr().err


def test_a_malformed_declaration_is_refused_at_parse_time(tmp_path):
    path = write(tmp_path, [])

    with pytest.raises(SystemExit):
        main(["import-learnpack", "--file", str(path), "--acl", "--generator", "nonsense"])
