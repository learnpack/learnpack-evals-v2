"""The ADR-0019 act, every acceptance and refusal path.

Two halves. The CLI half pins what a terminal sees — exit codes and the lines the gate
writes — and is the regression net for the rules having moved into a use case. The use-case
half pins the facts the refusals carry, which is what the second gate renders (ADR-0036 §4)
and what no stderr string can express.

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


def test_ratifications_are_on_the_public_surface(cleanup, unique, session, admin, patched_package):
    from app.modules.evaluation.public import EvaluationQueries

    admin_id, email = admin
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)

    assert EvaluationQueries(session).list_ratifications(v1) == []

    assert run_ratify_assessor(patched_package.name, "1", v1, email, []) == 0
    track_automated(cleanup, patched_package.name)

    listed = EvaluationQueries(session).list_ratifications(v1)
    assert len(listed) == 1
    assert listed[0].instrument_version_id == v1
    assert listed[0].ratified_at is not None


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


# ------------------------------------------------- the use case, and the facts it carries


@pytest.fixture
def ratify(session):
    from app.modules.evaluation.application.ratify_assessor import RatifyAssessor
    from app.modules.evaluation.infrastructure.gateways import DesignInstrumentGateway
    from app.modules.evaluation.infrastructure.repository import SqlAlchemyRatificationRepository
    from app.platform.uow import UnitOfWork

    use_case = RatifyAssessor(
        instruments=DesignInstrumentGateway(session),
        ratifications=SqlAlchemyRatificationRepository(session),
        uow=UnitOfWork(session),
    )

    def _ratify(assessor_id, package, instrument_version_id: str, by, confirmed=()):
        from app.modules.evaluation.application.ratify_assessor import RatifyAssessorCommand

        return use_case(
            RatifyAssessorCommand(
                assessor_id=assessor_id,
                instrument_id=package.instrument_id,
                instrument_version_id=instrument_version_id,
                coverage=package.coverage,
                ratified_by=by,
                confirmed=frozenset(confirmed),
            )
        )

    return _ratify


@pytest.fixture
def automated(session, cleanup, patched_package):
    """The assessor row the first ratification would have minted."""
    from app.modules.identity.application.register_automated_assessor import (
        RegisterAutomatedAssessor,
        RegisterAutomatedAssessorCommand,
    )

    registered = RegisterAutomatedAssessor(SqlAlchemyAssessorRepository(session))(
        RegisterAutomatedAssessorCommand(
            name=patched_package.name,
            version=patched_package.version,
            display_name=patched_package.display_name,
            source_config=patched_package.source_config,
        )
    )
    session.commit()
    cleanup["assessors"].append(str(registered.assessor.assessor_id))
    return registered.assessor.assessor_id


def _two_versions_apart(cleanup, unique, admin_id):
    """v1, then a v2 that changes one executed criterion and one abstained one."""
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    spec = copy_spec(unique, version="v2")
    executed = next(c for c in spec["criteria"] if c["id"] == "cr-course-has-development")
    executed["pass_condition"] = "At least THREE lessons follow the module-00 introduction."
    abstained = next(c for c in spec["criteria"] if c["id"] == "cr-arc-character")
    abstained["pass_condition"] = "The opening lesson introduces; the final lesson closes HARD."
    return v1, publish_instrument(cleanup, spec, admin_id), executed["pass_condition"]


def test_the_delta_says_what_changed_and_who_decides_it(
    cleanup, unique, admin, automated, ratify, patched_package
):
    from app.modules.evaluation.application.ratify_assessor import RatificationNeedsConfirmation

    admin_id, _ = admin
    v1, v2, new_text = _two_versions_apart(cleanup, unique, admin_id)
    ratify(automated, patched_package, v1, admin_id)

    with pytest.raises(RatificationNeedsConfirmation) as raised:
        ratify(automated, patched_package, v2, admin_id)

    refusal = raised.value
    assert refusal.previous_version_id == v1
    # Only the executed one is pending: an abstention realizes no normative text.
    assert [d.criterion_id for d in refusal.pending] == ["cr-course-has-development"]
    by_id = {d.criterion_id: d for d in refusal.deltas}
    assert by_id["cr-course-has-development"].disposition == "needs_confirmation"
    assert by_id["cr-course-has-development"].change == "changed"
    # The text to be confirmed travels with the refusal — the console shows it beside the
    # checkbox, so nobody has to go and look the criterion up.
    assert by_id["cr-course-has-development"].pass_condition == new_text
    assert by_id["cr-arc-character"].disposition == "abstained"


def test_confirming_the_pending_criterion_ratifies(
    cleanup, unique, session, admin, automated, ratify, patched_package
):
    admin_id, _ = admin
    v1, v2, _ = _two_versions_apart(cleanup, unique, admin_id)
    ratify(automated, patched_package, v1, admin_id)

    result = ratify(
        automated, patched_package, v2, admin_id, confirmed=["cr-course-has-development"]
    )
    assert result.newly_ratified is True
    assert {d.criterion_id: d.disposition for d in result.deltas} == {
        "cr-course-has-development": "confirmed",
        "cr-arc-character": "abstained",
    }
    assert ratifications(session, v2) == 1

    # Idempotent: the act says it did not happen again rather than inserting twice. The
    # delta is recomputed against v1 either way — being already ratified does not excuse
    # the decision, it only makes repeating it free.
    repeated = ratify(
        automated, patched_package, v2, admin_id, confirmed=["cr-course-has-development"]
    )
    assert repeated.newly_ratified is False
    assert ratifications(session, v2) == 1


def test_a_new_criterion_is_reported_as_new(
    cleanup, unique, admin, automated, ratify, patched_package
):
    from app.modules.evaluation.application.ratify_assessor import CoverageIncomplete

    admin_id, _ = admin
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    ratify(automated, patched_package, v1, admin_id)

    spec = copy_spec(unique, version="v2")
    extra = copy.deepcopy(spec["criteria"][0])
    extra["id"] = "cr-brand-new"
    spec["criteria"].append(extra)
    v2 = publish_instrument(cleanup, spec, admin_id)

    # A criterion the coverage does not decide never reaches the delta: it is a change of
    # the artifact, refused before anyone is asked to confirm anything (ADR-0018).
    with pytest.raises(CoverageIncomplete) as raised:
        ratify(automated, patched_package, v2, admin_id)
    assert raised.value.undecided == frozenset({"cr-brand-new"})


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
