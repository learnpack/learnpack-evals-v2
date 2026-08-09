"""Bulk registration through the CLI — the canonical JSON shape (ADR-0024).

Each entry declares its own generator: the key is required, null declares unknown, and a
missing key is an invalid row — silence is not a declaration. Registering *from a source*
(URL or local directory) is `register-package`'s job (ADR-0027, test_register_package_cli).
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

    assert run_import_learnpack(path) == 0
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

    assert run_import_learnpack(path) == 1
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

    assert run_import_learnpack(path) == 0
    assert track(cleanup, session, external_id)
    assert generator_of(session, external_id) is None


def test_the_retired_acl_flag_is_gone(tmp_path):
    """The slice-1 `--acl` seam retired with ADR-0027: the flag no longer parses."""
    path = write(tmp_path, [])

    with pytest.raises(SystemExit):
        main(["import-learnpack", "--file", str(path), "--acl"])
