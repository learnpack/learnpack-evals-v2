"""The calibration page's two endpoints: the registry as data, and the dry-run over HTTP.

Reuses the automated-flow fixtures (`profiled_course`, `patched_package`) and the
throwaway instrument-copy helpers: the preview must behave exactly like the CLI's
`evaluate --dry-run` — accept drafts, need no ratification, persist nothing — because it
IS the same use case behind a different door.
"""

# ruff: noqa: F811 — imported pytest fixtures are re-bound as test parameters by design.

import dataclasses
import time
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_automated_evaluation_flow import (  # noqa: F401 — fixtures resolved by name
    copy_spec,
    patched_package,
    profiled_course,
    publish_instrument,
    track_automated,
)
from test_instrument_authoring_api import import_spec

from app.cli import run_ratify_assessor
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.platform import observability


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

    hybrid = by_key[("drafts-hybrid", "8")]
    assert hybrid["instrument_id"] == "course-drafts-qa"
    assert hybrid["display_name"] == "drafts-hybrid v8"
    assert hybrid["uses_llm"] is True
    assert len(hybrid["executes"]) == 19 and len(hybrid["abstains"]) == 10
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
        "assessor_id",
        "lineage_versions",
    }

    assert by_key[("structural", "1")]["uses_llm"] is False
    assert by_key[("drafts-structural", "1")]["uses_llm"] is False


def test_assessor_packages_report_what_each_has_ratified(admin, cleanup, unique, patched_package):
    """The state the assessors page reads: a package declared in code with no identity row
    yet, and the one version of its lineage that a human has since made evaluable."""
    admin_id = admin.get("/me").json()["assessor_id"]
    published = publish_instrument(cleanup, copy_spec(unique), admin_id)
    draft = import_spec(cleanup, copy_spec(unique, version="v2"))

    def package_row() -> dict:
        listing = admin.get("/admin/assessor-packages")
        assert listing.status_code == 200, listing.text
        return next(p for p in listing.json() if p["name"] == patched_package.name)

    before = package_row()
    # No row at all until somebody ratifies: registration IS the first ratification.
    assert before["assessor_id"] is None
    assert {v["instrument_version_id"]: v["ratified"] for v in before["lineage_versions"]} == {
        published: False,
        draft: False,
    }

    assert (
        run_ratify_assessor(patched_package.name, "1", published, f"admin-{unique}@example.com", [])
        == 0
    )
    track_automated(cleanup, patched_package.name)

    after = package_row()
    assert after["assessor_id"] is not None
    versions = {v["instrument_version_id"]: v for v in after["lineage_versions"]}
    assert versions[published]["ratified"] is True
    assert versions[published]["ratified_at"] is not None
    # The act has an author, and the page names them.
    assert versions[published]["ratified_by_name"] == "Admin"
    # A draft is listed and never ratified: its remedy is publishing, not ratifying.
    assert versions[draft]["status"] == "draft"
    assert versions[draft]["ratified"] is False
    assert versions[draft]["ratified_by_name"] is None


# -------------------------------------------------------------------- quality reference


def test_quality_reference_requires_admin(evaluator_client):
    assert evaluator_client.get("/admin/reference/qualities").status_code == 403


def test_quality_reference_maps_qualities_to_dimensions(admin):
    """What the page's local fitness projection groups by — live reference data, the
    vocabulary as seeded (docs/seed/pedagogical-reference.yaml)."""
    response = admin.get("/admin/reference/qualities")
    assert response.status_code == 200, response.text
    by_quality = {row["quality_id"]: row["dimension_id"] for row in response.json()}
    assert by_quality["progression-cognitive-demand"] == "learning-progression"
    assert by_quality["objectives-observable"] == "objectives-quality"
    assert len(by_quality) >= 21  # the seeded vocabulary, at least


# ---------------------------------------------------------------------------- preview
#
# The dry-run is started, not awaited (it takes minutes with LLM criteria), so every test
# here does what the page does: start it, then read the run until it ends.


def start_run(client, package, content_id, instrument_version_id: str) -> str:
    response = client.post(
        "/admin/evaluations/preview", json=preview_body(package, content_id, instrument_version_id)
    )
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


def read_until_done(client, run_id: str, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/admin/evaluations/preview/{run_id}")
        assert response.status_code == 200, response.text
        run = response.json()
        if run["status"] != "running":
            return run
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} never finished")


def run_preview(client, package, content_id, instrument_version_id: str) -> dict:
    return read_until_done(client, start_run(client, package, content_id, instrument_version_id))


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
    run = run_preview(admin, patched_package, profiled_course, draft_id)
    assert run["status"] == "done" and run["error"] is None
    assert counts() == before  # zero writes: no evaluation, no judgment, no events

    body = run["result"]
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
    # The cause travels in the contract, empty on every state but execution_error.
    assert drift["execution_cause"] is None

    # The judgment rides along: camelCase evidence_basis (the domain's own vocabulary),
    # the excluded claims, and at least one finding carrying its quote.
    statuses = {c["claim_id"]: c["status"] for c in body["claims"]}
    assert statuses["cl-course-modular"] == "refuted"
    basis_keys = {key for c in body["claims"] for key in c["evidence_basis"]}
    assert basis_keys <= {
        "pass",
        "fail",
        "noEvidence",
        "notApplicable",
        "notAssessed",
        "executionError",
    }
    assert set(body["coverage"]["excludedClaims"]) == {
        "cl-objectives-declared",
        "cl-audience-declared",
    }
    assert any(
        f["criterion_id"] == "cr-module-structure-well-formed" and f["quote"]
        for f in body["findings"]
    )
    assert {m["metric_id"] for m in body["metrics"]}  # raw executor metrics travel too


def test_a_run_reports_each_criterion_as_it_lands(
    admin, cleanup, unique, patched_package, profiled_course
):
    """The progress the page shows while it waits: one step per EXECUTED criterion —
    a derived outcome runs no executor, so there is nothing to report about it."""
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)

    run = run_preview(admin, patched_package, profiled_course, draft_id)

    steps = run["steps"]
    executed = {o["criterion_id"] for o in run["result"]["outcomes"] if not o["derived"]}
    assert {step["label"] for step in steps if step["kind"] == "criterion"} == executed
    assert all(step["detail"] in {"pass", "fail"} for step in steps)
    assert all(step["ok"] for step in steps)  # a `fail` is a verdict, not a malfunction
    # Ordered in time and measured on the server, so the page needs no clock of its own.
    assert [step["at_ms"] for step in steps] == sorted(step["at_ms"] for step in steps)
    assert run["elapsed_ms"] >= 0 and run["finished_at"]


def test_preview_requires_admin(evaluator_client, patched_package, profiled_course):
    response = evaluator_client.post(
        "/admin/evaluations/preview",
        json=preview_body(patched_package, profiled_course, "any-version"),
    )
    assert response.status_code == 403


def test_reading_a_run_requires_admin(
    evaluator_client, admin, cleanup, unique, patched_package, profiled_course
):
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)
    run_id = start_run(admin, patched_package, profiled_course, draft_id)

    assert evaluator_client.get(f"/admin/evaluations/preview/{run_id}").status_code == 403
    assert evaluator_client.get(f"/admin/evaluations/preview/{run_id}/trace").status_code == 403


def test_an_unknown_run_is_404_and_says_why_it_could_be_gone(admin):
    response = admin.get(f"/admin/evaluations/preview/{uuid4()}")
    assert response.status_code == 404
    assert "in memory" in response.json()["detail"]


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
    assert "drafts-hybrid:8" in response.json()["detail"]  # the known list, like the CLI


def test_an_unknown_instrument_fails_the_run(admin, patched_package, profiled_course):
    """Discovered by the run, not by the request: every ending is read from one place."""
    run = run_preview(admin, patched_package, profiled_course, "does-not-exist")

    assert run["status"] == "failed" and run["result"] is None
    assert run["error"]["kind"] == "instrument_missing"
    assert "not found" in run["error"]["message"]


def test_a_content_without_an_ok_profile_fails_the_run(admin, cleanup, unique, patched_package):
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
    run = run_preview(admin, patched_package, unprofiled["content_id"], draft_id)

    assert run["status"] == "failed" and run["result"] is None
    assert run["error"]["kind"] == "profile_missing"
    assert "profile it first" in run["error"]["message"]


def test_an_assessor_past_the_failure_budget_fails_the_run(
    admin, cleanup, unique, session, monkeypatch, patched_package, profiled_course
):
    """ADR-0037 §3 through the HTTP door: with EVERY executor failing, the budget
    (int(0.25 × 9) = 2 tolerated) is exceeded and the run was not an evaluation — it ends
    with no verdict at all, nothing persisted, and the cause named so the page can say
    what to do about it."""

    def boom(spec, profile):
        raise AssessorExecutionError(
            "task 'outcomes_extraction': the model never satisfied the output contract",
            kind="contract",
            task="outcomes_extraction",
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
    before = session.execute(text("SELECT count(*) FROM evaluations")).scalar_one()

    run = run_preview(admin, broken, profiled_course, draft_id)

    assert run["status"] == "failed" and run["result"] is None
    assert run["error"]["kind"] == "assessor_failed"
    assert "never satisfied the output contract" in run["error"]["message"]
    assert session.execute(text("SELECT count(*) FROM evaluations")).scalar_one() == before
    # The criterion that blew up is in the log: the page shows where it stopped.
    assert any(
        not step["ok"] and "AssessorExecutionError" in step["detail"] for step in run["steps"]
    )


def test_a_single_failed_criterion_leaves_the_run_done_with_its_cause(
    admin, cleanup, unique, session, monkeypatch, patched_package, profiled_course
):
    """ADR-0037 through the HTTP door, below the budget: one degenerating executor inside
    an otherwise healthy dry run. The run finishes `done`, the failed criterion carries
    `execution_error` with its structured cause, coverage stays exact around it, its step
    is the red line — and still nothing persists (a dry run never does)."""

    def boom(spec, profile):
        raise AssessorExecutionError(
            "task 'probe': the model repeated itself", kind="degeneration", task="probe"
        )

    name = f"flaky-{unique}"
    flaky = dataclasses.replace(
        patched_package,
        name=name,
        executors={
            **patched_package.executors,
            "cr-module-structure-well-formed": boom,
        },
        source_config={**patched_package.source_config, "name": name},
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (name, flaky.version), flaky)
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)
    before = session.execute(text("SELECT count(*) FROM evaluations")).scalar_one()

    run = run_preview(admin, flaky, profiled_course, draft_id)

    assert run["status"] == "done" and run["error"] is None
    outcomes = {o["criterion_id"]: o for o in run["result"]["outcomes"]}
    assert len(outcomes) == 27  # exact coverage holds around the failure
    errored = outcomes["cr-module-structure-well-formed"]
    assert errored["outcome"] == "execution_error" and errored["derived"]
    assert errored["execution_cause"] == {
        "task": "probe",
        "kind": "degeneration",
        "message": "task 'probe': the model repeated itself",
    }
    assert run["result"]["coverage"]["criteria"]["executionError"] == 1
    assert session.execute(text("SELECT count(*) FROM evaluations")).scalar_one() == before
    assert any(
        not step["ok"] and step["label"] == "cr-module-structure-well-formed"
        for step in run["steps"]
    )


def test_the_trace_carries_every_llm_attempt_of_the_run(
    admin, cleanup, unique, monkeypatch, patched_package, profiled_course
):
    """The point of the whole thing: after a run, the prompt each task sent and the raw
    text it got back are readable — retries included, untruncated."""
    prompt = "classify these objectives verbatim" * 20

    def calls_a_model(spec, profile):
        for attempt, error in ((1, "HTTP 429"), (2, None)):
            observability.emit(
                observability.LlmCall(
                    task_id="objectives_classification",
                    attempt=attempt,
                    model_requested="vendor/model",
                    messages=({"role": "user", "content": prompt},),
                    sampling={"temperature": 0.0, "reasoning": {"effort": "none"}},
                    latency_ms=12,
                    model_answered=None if error else "vendor/model",
                    provider=None if error else "TheOneThatAnswered",
                    response_text=None if error else '{"objectives": []}',
                    finish_reason=None if error else "stop",
                    tokens_in=0 if error else 900,
                    tokens_out=0 if error else 30,
                    error=error,
                )
            )
        return patched_package.executors[spec.criterion_id](spec, profile)

    name = f"talkative-{unique}"
    talkative = dataclasses.replace(
        patched_package,
        name=name,
        executors={criterion_id: calls_a_model for criterion_id in patched_package.executors},
        source_config={**patched_package.source_config, "name": name},
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (name, talkative.version), talkative)
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)

    run_id = start_run(admin, talkative, profiled_course, draft_id)
    run = read_until_done(admin, run_id)
    assert run["status"] == "done"

    trace = admin.get(f"/admin/evaluations/preview/{run_id}/trace")
    assert trace.status_code == 200, trace.text
    calls = trace.json()["calls"]
    assert len(calls) == 2 * len([s for s in run["steps"] if s["kind"] == "criterion"])
    failed, succeeded = calls[0], calls[1]
    assert failed["error"] == "HTTP 429" and failed["attempt"] == 1
    assert succeeded["provider"] == "TheOneThatAnswered"
    assert succeeded["response_text"] == '{"objectives": []}'
    assert succeeded["messages"][0]["content"] == prompt  # whole, not abridged
    # How it was sampled travels too: it decides the answer as much as the prompt does.
    assert succeeded["sampling"] == {"temperature": 0.0, "reasoning": {"effort": "none"}}

    # The same records are the live progress the page reads while it waits.
    llm_steps = [step for step in run["steps"] if step["kind"] == "llm_call"]
    assert llm_steps[0]["label"] == "objectives_classification"
    assert "attempt 1 · HTTP 429" in llm_steps[0]["detail"] and not llm_steps[0]["ok"]
    assert "900→30 tokens" in llm_steps[1]["detail"]


def test_a_trace_is_empty_when_the_assessor_never_asks_a_model(
    admin, cleanup, unique, patched_package, profiled_course
):
    draft_id = import_spec(cleanup, copy_spec(unique), revise_definitions=True)
    run_id = start_run(admin, patched_package, profiled_course, draft_id)
    read_until_done(admin, run_id)

    trace = admin.get(f"/admin/evaluations/preview/{run_id}/trace").json()
    assert trace["calls"] == [] and trace["status"] == "done"
