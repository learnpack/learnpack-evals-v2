"""The ratification act's second gate (ADR-0036): every ending, as a client sees it.

The rules themselves are pinned against the use case in `test_ratify_assessor.py`. What
this file pins is the vocabulary the gate speaks — which ending is a 409 carrying data to
act on, which are 422s that name their cause, and that a refusal leaves the store exactly
as it found it.
"""

# ruff: noqa: F811 — imported pytest fixtures are re-bound as test parameters by design.

import copy
import dataclasses

import pytest
from sqlalchemy import text
from test_automated_evaluation_flow import (  # noqa: F401 — fixtures resolved by name
    copy_spec,
    patched_package,
    publish_instrument,
    track_automated,
)
from test_instrument_authoring_api import import_spec

from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def evaluator_client(as_user, cleanup, unique):
    client = as_user(f"user_eval_{unique}", f"eval-{unique}@example.com", "Eval")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    return client


def ratify(client, package, instrument_version_id: str, confirmed=()):
    return client.post(
        f"/admin/assessor-packages/{package.name}/{package.version}/ratify",
        json={"instrument_version_id": instrument_version_id, "confirmed": list(confirmed)},
    )


def automated_rows(session, name: str) -> int:
    return session.execute(
        text("SELECT count(*) FROM assessors WHERE source_config->>'name' = :name"),
        {"name": name},
    ).scalar_one()


def test_ratifying_requires_admin(evaluator_client, patched_package):
    assert ratify(evaluator_client, patched_package, "whatever").status_code == 403


def test_unknown_package_is_404(admin):
    response = admin.post(
        "/admin/assessor-packages/nobody/9/ratify", json={"instrument_version_id": "x"}
    )
    assert response.status_code == 404
    assert "nobody:9" in response.json()["detail"]


def test_the_first_ratification_registers_the_assessor(
    admin, cleanup, unique, session, patched_package
):
    admin_id = admin.get("/me").json()["assessor_id"]
    published = publish_instrument(cleanup, copy_spec(unique), admin_id)

    response = ratify(admin, patched_package, published)
    assert response.status_code == 200, response.text
    track_automated(cleanup, patched_package.name)

    body = response.json()
    assert body["newly_registered"] is True
    assert body["newly_ratified"] is True
    assert body["instrument_version_id"] == published

    # Idempotent, and honest about it: the act reports that neither happened again.
    again = ratify(admin, patched_package, published).json()
    assert again["newly_registered"] is False
    assert again["newly_ratified"] is False
    assert again["assessor_id"] == body["assessor_id"]
    assert automated_rows(session, patched_package.name) == 1


@pytest.mark.parametrize("cause", ["unknown", "draft", "foreign", "undecided"])
def test_each_refusal_is_a_422_that_names_its_cause(
    admin, cleanup, unique, session, patched_package, cause
):
    admin_id = admin.get("/me").json()["assessor_id"]

    if cause == "unknown":
        target, expected = "no-such-version", "not found"
    elif cause == "draft":
        target = import_spec(cleanup, copy_spec(unique))
        expected = "draft"
    elif cause == "foreign":
        foreign = copy.deepcopy(copy_spec(unique))
        foreign["instrument_id"] = f"qa-foreign-{unique}"
        target = publish_instrument(cleanup, foreign, admin_id)
        expected = "lineage"
    else:
        spec = copy_spec(unique)
        extra = copy.deepcopy(spec["criteria"][0])
        extra["id"] = "cr-brand-new"
        spec["criteria"].append(extra)
        target = publish_instrument(cleanup, spec, admin_id)
        expected = "cr-brand-new"

    response = ratify(admin, patched_package, target)
    assert response.status_code == 422, response.text
    assert expected in response.json()["detail"]
    # Nothing partial survives a refusal: the row the act would have minted is not there.
    assert automated_rows(session, patched_package.name) == 0


def test_a_drifted_source_config_is_422(
    admin, cleanup, unique, session, patched_package, monkeypatch
):
    admin_id = admin.get("/me").json()["assessor_id"]
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert ratify(admin, patched_package, v1).status_code == 200
    track_automated(cleanup, patched_package.name)

    drifted = dataclasses.replace(
        patched_package,
        source_config={
            **patched_package.source_config,
            "coverage": {"executes": [], "abstains": {}},
        },
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (patched_package.name, "1"), drifted)

    v2 = publish_instrument(cleanup, copy_spec(unique, version="v2"), admin_id)
    response = ratify(admin, drifted, v2)
    assert response.status_code == 422
    assert "bump VERSION" in response.json()["detail"]


def test_a_changed_executed_criterion_is_a_409_carrying_the_decision(
    admin, cleanup, unique, session, patched_package
):
    admin_id = admin.get("/me").json()["assessor_id"]
    v1 = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert ratify(admin, patched_package, v1).status_code == 200
    track_automated(cleanup, patched_package.name)

    spec = copy_spec(unique, version="v2")
    changed = next(c for c in spec["criteria"] if c["id"] == "cr-course-has-development")
    changed["pass_condition"] = "At least THREE lessons follow the module-00 introduction."
    abstained = next(c for c in spec["criteria"] if c["id"] == "cr-arc-character")
    abstained["pass_condition"] = "The opening lesson introduces; the final lesson closes HARD."
    v2 = publish_instrument(cleanup, spec, admin_id)

    refused = ratify(admin, patched_package, v2)
    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    assert detail["previous_version_id"] == v1
    # Only the executed one, and with the text the console puts beside the checkbox.
    assert [c["criterion_id"] for c in detail["criteria"]] == ["cr-course-has-development"]
    assert detail["criteria"][0]["change"] == "changed"
    assert detail["criteria"][0]["pass_condition"] == changed["pass_condition"]
    assert (
        session.execute(
            text("SELECT count(*) FROM assessor_ratifications WHERE instrument_version_id = :id"),
            {"id": v2},
        ).scalar_one()
        == 0
    )

    accepted = ratify(admin, patched_package, v2, confirmed=["cr-course-has-development"])
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["newly_ratified"] is True
