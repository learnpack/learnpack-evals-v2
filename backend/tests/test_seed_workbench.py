"""The local workbench (ADR-0045): one manifest, and the acts that make a database able to
measure.

What is pinned here is the three properties the command is worth having for. It installs
exactly what the manifest names — instruments published, extractions accepted, lineages
registered, and every assessor package of a published lineage ratified. It can be run again
without changing anything. And it refuses outside local mode, because publishing an
instrument and ratifying an assessor are human acts everywhere else (ADR-0012, ADR-0019).
"""

import pathlib

import pytest
import yaml
from sqlalchemy import text

from app.cli import WORKBENCH_MANIFEST, _instrument_identity, run_seed_workbench
from app.config import get_settings
from app.modules.content_profiling.infrastructure.adapters import ADAPTERS_BY_FORMAT
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS

MANIFEST = yaml.safe_load(WORKBENCH_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture
def local_auth(monkeypatch):
    """Declare the mode the command requires, rather than inheriting it.

    A developer's `.env` says `AUTH_MODE=local` and CI has no `.env` at all, so a test that
    reads whatever the environment happens to say passes here and fails there — which is what
    it did. The mode is part of what these tests are about, so they state it.
    """
    monkeypatch.setenv("AUTH_MODE", "local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def workbench(cleanup, requires_db, local_auth):
    """Run the real manifest, and track everything it writes so the suite's database is left
    as it was found. The acceptance matters most: it is global, and a stray one would
    auto-profile every content registered by every later test."""
    for relative in MANIFEST["instruments"]:
        _, version_id = _instrument_identity(WORKBENCH_MANIFEST.parent / relative)
        cleanup["instruments"].append(version_id)
    for package_format in MANIFEST["extractions"]:
        cleanup["acceptances"].append(
            (package_format, ADAPTERS_BY_FORMAT[package_format].adapter_version)
        )

    assert run_seed_workbench() == 0

    from app.platform.db import SessionLocal

    with SessionLocal() as session:
        cleanup["assessors"].extend(
            row.id
            for row in session.execute(
                text("SELECT id FROM assessors WHERE kind = 'automated' OR email = :e"),
                {"e": "admin@local.dev"},
            )
        )
        cleanup["generator_lineages"].extend(
            row.id
            for row in session.execute(
                text("SELECT id FROM generators WHERE name = ANY(:names)"),
                {"names": MANIFEST["generators"]},
            )
        )
    return MANIFEST


def test_the_manifest_id_is_the_one_the_importer_mints():
    """Anti-drift, and the reason the manifest lists FILES rather than version ids: the id is
    read off the same two fields the importer builds it from, so there is no second place to
    write `course-drafts-qa-v9` and get it wrong."""
    for relative in MANIFEST["instruments"]:
        spec_file = WORKBENCH_MANIFEST.parent / relative
        lineage, version_id = _instrument_identity(spec_file)
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))

        assert version_id == f"{spec['instrument_id']}-{spec['version']}"
        assert lineage == spec["instrument_id"]
        assert spec_file.name == f"{version_id}.yaml"


def test_the_manifest_publishes_one_version_per_lineage():
    """Clause 5: the published version is what every assessor of that lineage is ratified
    against, so two of them would leave the command choosing a norm."""
    lineages = [
        _instrument_identity(WORKBENCH_MANIFEST.parent / relative)[0]
        for relative in MANIFEST["instruments"]
    ]

    assert len(lineages) == len(set(lineages))


def test_it_publishes_accepts_ratifies_and_registers(workbench, session):
    """The four acts, read back from the store — not from what the command printed."""
    for relative in MANIFEST["instruments"]:
        _, version_id = _instrument_identity(WORKBENCH_MANIFEST.parent / relative)
        status = session.execute(
            text("SELECT status FROM instrument_versions WHERE id = :id"), {"id": version_id}
        ).scalar()
        assert status == "published"

    for package_format in MANIFEST["extractions"]:
        assert session.execute(
            text(
                "SELECT 1 FROM extraction_acceptances WHERE package_format = :f "
                "AND adapter_version = :v"
            ),
            {"f": package_format, "v": ADAPTERS_BY_FORMAT[package_format].adapter_version},
        ).scalar()

    for name in MANIFEST["generators"]:
        assert session.execute(
            text("SELECT 1 FROM generators WHERE name = :n"), {"n": name}
        ).scalar()

    # Which assessors exist is the code registry's answer (ADR-0016), so this asserts over the
    # registry rather than a list repeated here: adding a package must not leave this green.
    published = {
        _instrument_identity(WORKBENCH_MANIFEST.parent / relative)
        for relative in MANIFEST["instruments"]
    }
    for package in AUTOMATED_ASSESSORS.values():
        version_id = next(
            (version for lineage, version in published if lineage == package.instrument_id), None
        )
        if version_id is None:
            continue
        ratified = session.execute(
            text(
                "SELECT 1 FROM assessor_ratifications r JOIN assessors a ON a.id = r.assessor_id "
                "WHERE r.instrument_version_id = :v "
                "AND a.source_config->>'name' = :n AND a.source_config->>'version' = :ver"
            ),
            {"v": version_id, "n": package.name, "ver": package.version},
        ).scalar()
        assert ratified, f"{package.display_name} was not ratified against {version_id}"


def test_running_it_again_changes_nothing(workbench, session, capsys):
    """Idempotent by asking, not by swallowing: a published version is left alone, an
    existing lineage is reported. Swallowing the refusals would also hide ADR-0031's
    near-miss guard firing on a real typo."""
    before = session.execute(text("SELECT count(*) FROM assessor_ratifications")).scalar()
    capsys.readouterr()

    assert run_seed_workbench() == 0

    out = capsys.readouterr().out
    assert "is already published" in out
    assert "is already registered" in out
    assert "already ratified" in out
    assert session.execute(text("SELECT count(*) FROM assessor_ratifications")).scalar() == before


def test_two_versions_of_one_lineage_are_refused_before_anything_is_written(
    tmp_path, capsys, requires_db, session, local_auth
):
    """It refuses rather than resolving: which version an assessor should judge with is the
    decision the manifest exists to record.

    And it refuses before writing, which is the half that cannot be got wrong twice:
    publishing is irreversible, so a manifest refused halfway would leave a published version
    behind that no rerun can take back.
    """
    instruments = WORKBENCH_MANIFEST.parent / "instruments"
    manifest = tmp_path / "workbench.yaml"
    # Absolute entries: a relative one is read against the manifest's own folder, which is
    # the repo's `docs/seed/` for the real file and a throwaway directory here.
    manifest.write_text(
        yaml.safe_dump(
            {
                "instruments": [
                    str(instruments / "course-drafts-qa-v8.yaml"),
                    str(instruments / "course-drafts-qa-v9.yaml"),
                ]
            }
        ),
        encoding="utf-8",
    )

    assert run_seed_workbench(manifest) == 1

    assert "two versions of 'course-drafts-qa'" in capsys.readouterr().err
    assert not session.execute(
        text("SELECT 1 FROM instrument_versions WHERE id LIKE 'course-drafts-qa-%'")
    ).scalar()


def test_a_manifest_naming_a_missing_file_writes_nothing(
    tmp_path, capsys, requires_db, session, local_auth
):
    """Same rule, the other way it goes wrong: a path that drifted must not publish whatever
    came before it in the list."""
    manifest = tmp_path / "workbench.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "instruments": [
                    str(WORKBENCH_MANIFEST.parent / "instruments" / "learnpack-course-qa-v1.yaml"),
                    str(tmp_path / "gone.yaml"),
                ]
            }
        ),
        encoding="utf-8",
    )

    assert run_seed_workbench(manifest) == 1

    assert "does not exist" in capsys.readouterr().err
    assert not session.execute(
        text("SELECT 1 FROM instrument_versions WHERE id = 'learnpack-course-qa-v1'")
    ).scalar()


def test_it_refuses_outside_local_mode(monkeypatch, capsys):
    """The gate of clause 2, and the one invariant this command must not be able to weaken:
    outside a dev box, the person who publishes an instrument is a person."""
    monkeypatch.setenv("AUTH_MODE", "clerk")
    get_settings.cache_clear()
    try:
        assert run_seed_workbench() == 1
        assert "AUTH_MODE=local" in capsys.readouterr().err
    finally:
        get_settings.cache_clear()


def test_the_manifest_names_files_that_exist():
    """A manifest is data under review, and a path that has drifted is a setup that fails at
    the one moment nobody has a working store to debug it with."""
    for relative in MANIFEST["instruments"]:
        assert (WORKBENCH_MANIFEST.parent / relative).is_file()
    for package_format in MANIFEST["extractions"]:
        assert package_format in ADAPTERS_BY_FORMAT
    assert isinstance(WORKBENCH_MANIFEST.parent, pathlib.Path)
