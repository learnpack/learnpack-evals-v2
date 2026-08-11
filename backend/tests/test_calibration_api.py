"""The calibration page's two endpoints: the registry as data, and the dry-run over HTTP.

Reuses the automated-flow fixtures (`profiled_course`, `patched_package`) and the
throwaway instrument-copy helpers: the preview must behave exactly like the CLI's
`evaluate --dry-run` — accept drafts, need no ratification, persist nothing — because it
IS the same use case behind a different door.
"""

# ruff: noqa: F811 — imported pytest fixtures are re-bound as test parameters by design.

import dataclasses

import pytest
from sqlalchemy import text
from test_automated_evaluation_flow import (  # noqa: F401 — fixtures resolved by name
    copy_spec,
    patched_package,
    profiled_course,
)
from test_instrument_authoring_api import import_spec

from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError


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


def preview_body(package, content_id, instrument_version_id: str) -> dict:
    return {
        "content_id": str(content_id),
        "instrument_version_id": instrument_version_id,
        "assessor_name": package.name,
        "assessor_version": package.version,
    }


# ------------------------------------------------------------------- assessor packages


def test_assessor_packages_require_admin(evaluator_client):
    assert evaluator_client.get("/admin/assessor-packages").status_code == 403


def test_assessor_packages_list_the_registry_without_its_internals(admin):
    response = admin.get("/admin/assessor-packages")
    assert response.status_code == 200, response.text
    by_key = {(p["name"], p["version"]): p for p in response.json()}

    hybrid = by_key[("drafts-hybrid", "1")]
    assert hybrid["instrument_id"] == "course-drafts-qa"
    assert hybrid["display_name"] == "drafts-hybrid v1"
    assert hybrid["uses_llm"] is True
    assert len(hybrid["executes"]) == 12 and len(hybrid["abstains"]) == 17
    # Abstention reasons are data the page shows; executors and source_config are not.
    assert all(isinstance(reason, str) and reason for reason in hybrid["abstains"].values())
    assert set(hybrid) == {
        "name",
        "version",
        "display_name",
        "instrument_id",
        "executes",
        "abstains",
        "uses_llm",
    }

    assert by_key[("structural", "1")]["uses_llm"] is False
    assert by_key[("drafts-structural", "1")]["uses_llm"] is False


# ---------------------------------------------------------------------------- preview


def test_preview_runs_a_draft_and_persists_nothing(
    admin, cleanup, unique, session, patched_package, profiled_course
):
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)

    def counts() -> tuple[int, int, int]:
        return (
            session.execute(text("SELECT count(*) FROM evaluations")).scalar_one(),
            session.execute(text("SELECT count(*) FROM quality_judgments")).scalar_one(),
            session.execute(text("SELECT count(*) FROM events")).scalar_one(),
        )

    before = counts()
    response = admin.post(
        "/admin/evaluations/preview", json=preview_body(patched_package, profiled_course, draft_id)
    )
    assert response.status_code == 200, response.text
    assert counts() == before  # zero writes: no evaluation, no judgment, no events

    body = response.json()
    assert body["persisted"] is False
    assert body["instrument_status"] == "draft"
    assert body["assessor"] == {
        "name": patched_package.name,
        "version": "1",
        "display_name": patched_package.display_name,
    }

    # Exact coverage, and the frozen course's real numbering drift comes through executed.
    outcomes = {o["criterion_id"]: o for o in body["outcomes"]}
    assert len(outcomes) == 27
    drift = outcomes["cr-module-structure-well-formed"]
    assert drift["outcome"] == "fail" and not drift["derived"]
    assert "drift" in drift["failure_mode"].lower() and drift["quote"]

    # The judgment rides along: camelCase evidence_basis (the domain's own vocabulary),
    # the excluded claims, and at least one finding carrying its quote.
    statuses = {c["claim_id"]: c["status"] for c in body["claims"]}
    assert statuses["cl-course-modular"] == "refuted"
    basis_keys = {key for c in body["claims"] for key in c["evidence_basis"]}
    assert basis_keys <= {"pass", "fail", "noEvidence", "notApplicable", "notAssessed"}
    assert set(body["coverage"]["excludedClaims"]) == {
        "cl-objectives-declared",
        "cl-audience-declared",
    }
    assert any(
        f["criterion_id"] == "cr-module-structure-well-formed" and f["quote"]
        for f in body["findings"]
    )
    assert {m["metric_id"] for m in body["metrics"]}  # raw executor metrics travel too


def test_preview_requires_admin(evaluator_client, patched_package, profiled_course):
    response = evaluator_client.post(
        "/admin/evaluations/preview",
        json=preview_body(patched_package, profiled_course, "any-version"),
    )
    assert response.status_code == 403


def test_preview_with_an_unknown_assessor_is_404_and_names_the_registry(admin, profiled_course):
    response = admin.post(
        "/admin/evaluations/preview",
        json={
            "content_id": str(profiled_course),
            "instrument_version_id": "any-version",
            "assessor_name": "no-such-assessor",
            "assessor_version": "9",
        },
    )
    assert response.status_code == 404
    assert "drafts-hybrid:1" in response.json()["detail"]  # the known list, like the CLI


def test_preview_with_an_unknown_instrument_is_404(admin, patched_package, profiled_course):
    response = admin.post(
        "/admin/evaluations/preview",
        json=preview_body(patched_package, profiled_course, "does-not-exist"),
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_preview_without_an_ok_profile_is_409(admin, cleanup, unique, patched_package):
    unprofiled = admin.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"unprofiled-{unique}",
            "generator_version_id": None,
        },
    ).json()
    cleanup["contents"].append(unprofiled["content_id"])

    # The instrument gate runs first, so a real draft is needed to reach the profile gate.
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)
    response = admin.post(
        "/admin/evaluations/preview",
        json=preview_body(patched_package, unprofiled["content_id"], draft_id),
    )
    assert response.status_code == 409
    assert "profile it first" in response.json()["detail"]


def test_an_assessor_that_cannot_judge_is_a_502(
    admin, cleanup, unique, monkeypatch, patched_package, profiled_course
):
    """ADR-0034 clause 4 through the HTTP door: the judge's irrecoverable failure is an
    upstream fault (502), nothing persisted, and the detail says retrying is fine."""

    def boom(spec, profile):
        raise AssessorExecutionError(
            "task 'outcomes_extraction': the model never satisfied the output contract"
        )

    name = f"broken-{unique}"
    broken = dataclasses.replace(
        patched_package,
        name=name,
        executors={criterion_id: boom for criterion_id in patched_package.executors},
        source_config={**patched_package.source_config, "name": name},
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (name, broken.version), broken)
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)

    response = admin.post(
        "/admin/evaluations/preview", json=preview_body(broken, profiled_course, draft_id)
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "could not produce a verdict" in detail and "nothing persisted" in detail
