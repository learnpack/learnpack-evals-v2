"""RegisterAutomatedAssessor — the get-or-create behind the first ratification.

The row appears the first time somebody ratifies (ADR-0019 §2), and its one refusal is
what keeps `(name, version)` naming a single judge (ADR-0016 §2).
"""

import pytest

from app.modules.identity.application.register_automated_assessor import (
    AutomatedAssessorDrifted,
    RegisterAutomatedAssessor,
    RegisterAutomatedAssessorCommand,
)
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository


@pytest.fixture
def register(session):
    return RegisterAutomatedAssessor(SqlAlchemyAssessorRepository(session))


@pytest.fixture
def command(unique):
    name, lineage = f"structural-{unique}", f"qa-copy-{unique}"
    return RegisterAutomatedAssessorCommand(
        name=name,
        version="1",
        display_name=f"Structural {unique}",
        source_config={
            "name": name,
            "version": "1",
            "instrumentId": lineage,
            "coverage": {"executes": ["cr-one"], "abstains": {}},
        },
    )


def test_first_call_mints_the_row_and_the_second_finds_it(register, command, session, cleanup):
    first = register(command)
    session.commit()
    cleanup["assessors"].append(str(first.assessor.assessor_id))

    assert first.newly_registered is True
    assert first.assessor.kind == "automated"
    assert first.assessor.automated is not None
    assert first.assessor.automated.name == command.name
    assert first.assessor.automated.instrument_id == command.source_config["instrumentId"]

    second = register(command)
    assert second.newly_registered is False
    assert second.assessor.assessor_id == first.assessor.assessor_id


def test_a_drifted_source_config_is_refused(register, command, session, cleanup):
    registered = register(command)
    session.commit()
    cleanup["assessors"].append(str(registered.assessor.assessor_id))

    # Same (name, version), different declared coverage: the artifact changed without a
    # version bump, so the two would be one identity naming two judges.
    drifted = RegisterAutomatedAssessorCommand(
        name=command.name,
        version=command.version,
        display_name=command.display_name,
        source_config={**command.source_config, "coverage": {"executes": [], "abstains": {}}},
    )
    with pytest.raises(AutomatedAssessorDrifted, match="bump VERSION"):
        register(drifted)


def test_the_row_is_not_committed_by_the_use_case(register, command, session):
    """Registering and ratifying are one act in one transaction (ADR-0036 §3): a rollback
    of the ratification must take the assessor with it."""
    register(command)
    session.rollback()

    assert SqlAlchemyAssessorRepository(session).get_automated(command.name, "1") is None
