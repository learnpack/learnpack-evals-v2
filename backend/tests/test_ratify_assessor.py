"""ratify-assessor — the ADR-0019 act, every acceptance and refusal path.

Reuses the throwaway-lineage helpers of the flow test: a clone of the `structural`
package bound to `qa-copy-<unique>`, published copies of the real instrument as the
lineage's versions.
"""

import copy
import dataclasses

import pytest
from sqlalchemy import text
from test_automated_evaluation_flow import copy_spec, publish_instrument, track_automated
from test_instrument_authoring_api import import_spec

from app.cli import run_ratify_assessor
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository


@pytest.fixture
def admin(register_assessor, unique):
    email = f"admin-{unique}@example.com"
    assessor_id = register_assessor(f"user_admin_{unique}", email, "Admin")
    return assessor_id, email


@pytest.fixture
def patched_package(unique, monkeypatch):
    base = AUTOMATED_ASSESSORS[("structural", "1")]
    name = f"structural-{unique}"
    lineage = f"qa-copy-{unique}"
    package = dataclasses.replace(
        base,
        name=name,
        instrument_id=lineage,
        source_config={**base.source_config, "name": name, "instrumentId": lineage},
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (name, base.version), package)
    return package


def ratifications(session, instrument_version_id: str) -> int:
    return session.execute(
        text("SELECT count(*) FROM assessor_ratifications WHERE instrument_version_id = :id"),
        {"id": instrument_version_id},
    ).scalar_one()


def test_initial_registration_is_the_first_ratification(
    cleanup, unique, session, admin, patched_package
):
    admin_id, email = admin
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)

    assert run_ratify_assessor(patched_package.name, "1", v1, email, []) == 0
    track_automated(cleanup, patched_package.name)

    row = SqlAlchemyAssessorRepository(session).get_automated(patched_package.name, "1")
    assert row is not None
    assert row.source_config == patched_package.source_config
    assert ratifications(session, v1) == 1

    # Re-ratifying is idempotent.
    assert run_ratify_assessor(patched_package.name, "1", v1, email, []) == 0
    assert ratifications(session, v1) == 1


def test_drafts_and_foreign_lineages_are_rejected(
    cleanup, unique, session, admin, patched_package, capsys
):
    admin_id, email = admin
    draft = import_spec(cleanup, copy_spec(unique))
    assert run_ratify_assessor(patched_package.name, "1", draft, email, []) == 1
    assert "dry-run" in capsys.readouterr().err  # points at the calibration path

    foreign = copy.deepcopy(copy_spec(unique))
    foreign["instrument_id"] = f"qa-foreign-{unique}"
    foreign_id = publish_instrument(cleanup, foreign, admin_id)
    assert run_ratify_assessor(patched_package.name, "1", foreign_id, email, []) == 1
    assert "lineage" in capsys.readouterr().err


def test_undecided_criteria_block_the_ratification(
    cleanup, unique, session, admin, patched_package, capsys
):
    admin_id, email = admin
    spec = copy_spec(unique)
    extra = copy.deepcopy(spec["criteria"][0])
    extra["id"] = "cr-brand-new"
    spec["criteria"].append(extra)
    version_id = publish_instrument(cleanup, spec, admin_id)

    assert run_ratify_assessor(patched_package.name, "1", version_id, email, []) == 1
    err = capsys.readouterr().err
    assert "cr-brand-new" in err and "new assessor version" in err
    assert ratifications(session, version_id) == 0


def test_unchanged_second_version_ratifies_alone(cleanup, unique, session, admin, patched_package):
    admin_id, email = admin
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", v1, email, []) == 0
    track_automated(cleanup, patched_package.name)

    v2 = publish_instrument(cleanup, copy_spec(unique, version="v2"), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", v2, email, []) == 0
    assert ratifications(session, v2) == 1


def test_changed_executed_criterion_demands_confirmation(
    cleanup, unique, session, admin, patched_package, capsys
):
    admin_id, email = admin
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", v1, email, []) == 0
    track_automated(cleanup, patched_package.name)

    spec = copy_spec(unique, version="v2")
    changed = next(c for c in spec["criteria"] if c["id"] == "cr-course-has-development")
    changed["pass_condition"] = "At least THREE lessons follow the module-00 introduction."
    v2 = publish_instrument(cleanup, spec, admin_id)

    assert run_ratify_assessor(patched_package.name, "1", v2, email, []) == 1
    assert "--confirm cr-course-has-development" in capsys.readouterr().err
    assert ratifications(session, v2) == 0

    assert (
        run_ratify_assessor(patched_package.name, "1", v2, email, ["cr-course-has-development"])
        == 0
    )
    assert ratifications(session, v2) == 1


def test_changed_abstained_criterion_is_informational_only(
    cleanup, unique, session, admin, patched_package, capsys
):
    admin_id, email = admin
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", v1, email, []) == 0
    track_automated(cleanup, patched_package.name)

    spec = copy_spec(unique, version="v2")
    changed = next(c for c in spec["criteria"] if c["id"] == "cr-arc-character")
    changed["pass_condition"] = "The opening lesson introduces; the final lesson closes HARD."
    v2 = publish_instrument(cleanup, spec, admin_id)

    # An abstention realizes no normative text: no --confirm needed (ADR-0019 §3).
    assert run_ratify_assessor(patched_package.name, "1", v2, email, []) == 0
    assert "cr-arc-character" in capsys.readouterr().out
    assert ratifications(session, v2) == 1


def test_source_config_drift_is_rejected(
    cleanup, unique, session, admin, patched_package, monkeypatch, capsys
):
    admin_id, email = admin
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", v1, email, []) == 0
    track_automated(cleanup, patched_package.name)

    # Same (name, version), different declared coverage: the artifact changed without a
    # version bump — exactly what ADR-0016 clause 2 forbids.
    drifted = dataclasses.replace(
        patched_package,
        source_config={
            **patched_package.source_config,
            "coverage": {"executes": [], "abstains": {}},
        },
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (patched_package.name, "1"), drifted)

    v2 = publish_instrument(cleanup, copy_spec(unique, version="v2"), admin_id)
    assert run_ratify_assessor(patched_package.name, "1", v2, email, []) == 1
    assert "bump VERSION" in capsys.readouterr().err
