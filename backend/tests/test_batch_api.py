"""The console's door onto a batch: start it, read it, stop it (ADR-0040).

The evaluation itself is faked at the same seam the unit tests use, because what is under
test here is the HTTP contract — which refusals get which code, what a page can read while a
run advances, and that the durable count comes from what was PERSISTED rather than from a run
object that dies with the process.
"""

# ruff: noqa: F811 — imported pytest fixtures are re-bound as test parameters by design.

import threading
import time
from uuid import uuid4

import pytest
from test_automated_evaluation_flow import (  # noqa: F401 — fixtures resolved by name
    copy_spec,
    patched_package,
    publish_instrument,
    track_automated,
)
from test_studies_api import declare, register_brief, register_content

from app.cli import run_ratify_assessor
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.platform import batch_runs as module


@pytest.fixture
def admin(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


@pytest.fixture
def open_study(admin, cleanup, unique, patched_package):
    """A study of two courses, pinned to a ratified instrument version and open."""
    admin_id = admin.get("/me").json()["assessor_id"]
    version_id = publish_instrument(cleanup, copy_spec(unique), admin_id)
    assert (
        run_ratify_assessor(
            patched_package.name, "1", version_id, f"admin-{unique}@example.com", []
        )
        == 0
    )
    assessor_id = track_automated(cleanup, patched_package.name)

    study_id = declare(admin, cleanup)
    brief_id = register_brief(admin, cleanup)
    register_content(admin, cleanup, unique, "one", brief_id)
    register_content(admin, cleanup, unique, "two", brief_id)
    admin.post(f"/admin/studies/{study_id}/pin", json={"instrument_version_id": version_id})
    pinned = admin.post(f"/admin/studies/{study_id}/assessor", json={"assessor_id": assessor_id})
    assert pinned.status_code == 200, pinned.text
    admin.post(f"/admin/studies/{study_id}/dataset", json={"brief_ids": [brief_id]})
    admin.post(f"/admin/studies/{study_id}/open")
    return study_id, version_id


def start_body(package, **overrides) -> dict:
    return {
        "assessor_name": package.name,
        "assessor_version": package.version,
        **overrides,
    }


def finished(admin, study_id: str, run_id: str) -> dict:
    """Poll the run the way the page does, until it stops running."""
    for _ in range(500):
        body = admin.get(f"/admin/studies/{study_id}/evaluations/{run_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.01)
    raise AssertionError("the run never ended")


# ------------------------------------------------------------------ starting


def test_starting_answers_202_with_an_id_and_the_run_reports_every_course(
    admin, open_study, patched_package, monkeypatch
):
    monkeypatch.setattr(module, "_run_use_case", lambda run, course: uuid4())
    study_id, version_id = open_study

    started = admin.post(f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package))
    assert started.status_code == 202, started.text
    run_id = started.json()["run_id"]

    body = finished(admin, study_id, run_id)
    assert body["status"] == "done"
    assert (body["total"], body["evaluated"], body["failed"]) == (2, 2, 0)
    assert body["instrument_version_id"] == version_id
    assert body["assessor"] == patched_package.display_name
    assert {c["status"] for c in body["courses"]} == {"evaluated"}
    assert all(c["brief_id"] for c in body["courses"])  # the fitness axis travels here too


def test_the_study_decides_the_assessor_and_a_disagreement_is_refused(
    admin, open_study, patched_package, monkeypatch
):
    """The request no longer chooses (ADR-0042 §10). Naming nobody runs the study's own
    judge; naming somebody else is refused rather than reconciled, because either answer
    would be silent — one evaluates under a judge nobody picked, the other ignores what was
    typed."""
    monkeypatch.setattr(module, "_run_use_case", lambda run, course: uuid4())
    study_id, _ = open_study

    silent = admin.post(f"/admin/studies/{study_id}/evaluations", json={})
    assert silent.status_code == 202, silent.text
    assert finished(admin, study_id, silent.json()["run_id"])["assessor"] == (
        patched_package.display_name
    )

    agreeing = admin.post(
        f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package)
    )
    assert agreeing.status_code == 202, agreeing.text
    finished(admin, study_id, agreeing.json()["run_id"])

    stranger_name, stranger_version = next(
        key for key in sorted(AUTOMATED_ASSESSORS) if key[0] != patched_package.name
    )
    disagreeing = admin.post(
        f"/admin/studies/{study_id}/evaluations",
        json={"assessor_name": stranger_name, "assessor_version": stranger_version},
    )
    assert disagreeing.status_code == 422, disagreeing.text
    assert disagreeing.json()["detail"]["kind"] == "assessor_mismatch"

    # Half a declaration is refused too. Ignoring it would run under the pin while the
    # caller believes it asked for something else, which is the outcome this path exists
    # to make impossible.
    half = admin.post(
        f"/admin/studies/{study_id}/evaluations", json={"assessor_name": stranger_name}
    )
    assert half.status_code == 422, half.text
    assert half.json()["detail"]["kind"] == "assessor_half_named"


def test_an_unknown_assessor_is_404_and_a_study_that_cannot_run_is_422(
    admin, cleanup, unique, patched_package
):
    """The refusals a page must render differently: one is a bad request, the other is a
    state the operator can fix — and each says which."""
    study_id = declare(admin, cleanup)  # declared, nothing pinned, no dataset

    unknown = admin.post(
        f"/admin/studies/{study_id}/evaluations",
        json={"assessor_name": "nope", "assessor_version": "9"},
    )
    assert unknown.status_code == 404

    refused = admin.post(f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package))
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["kind"] == "study_not_open"

    assert (
        admin.post(
            f"/admin/studies/{uuid4()}/evaluations", json=start_body(patched_package)
        ).status_code
        == 404
    )


def test_a_second_run_over_the_same_courses_is_409_while_the_first_is_alive(
    admin, open_study, patched_package, monkeypatch
):
    """Two batches over one course decide by arrival order, since every reader takes the
    most recent judgment. The conflict is refused rather than explained afterwards."""
    holding = threading.Event()

    def held(run, course):
        holding.wait(timeout=5)
        return uuid4()

    monkeypatch.setattr(module, "_run_use_case", held)
    study_id, _ = open_study
    first = admin.post(f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package))
    assert first.status_code == 202

    second = admin.post(f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package))

    assert second.status_code == 409, second.text
    assert second.json()["detail"]["kind"] == "overlapping_run"
    holding.set()
    finished(admin, study_id, first.json()["run_id"])


# ------------------------------------------------------------------ reading and stopping


def test_an_unknown_run_is_404_and_says_why_it_might_be_gone(admin, open_study):
    study_id, _ = open_study
    response = admin.get(f"/admin/studies/{study_id}/evaluations/{uuid4()}")
    assert response.status_code == 404
    assert "persisted either way" in response.json()["detail"]


def test_cancelling_stops_the_run_and_is_idempotent(
    admin, open_study, patched_package, monkeypatch
):
    holding = threading.Event()
    seen: list[str] = []

    def fake(run, course):
        seen.append(course.external_id)
        holding.wait(timeout=5)
        return uuid4()

    monkeypatch.setattr(module, "_run_use_case", fake)
    study_id, _ = open_study
    run_id = admin.post(
        f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package, concurrency=1)
    ).json()["run_id"]
    while not seen:
        time.sleep(0.01)

    cancelled = admin.post(f"/admin/studies/{study_id}/evaluations/{run_id}/cancel")
    assert cancelled.status_code == 202, cancelled.text
    holding.set()

    body = finished(admin, study_id, run_id)
    assert body["status"] == "cancelled"
    # The one in flight finished and persisted; the other never started.
    assert {c["status"] for c in body["courses"]} == {"evaluated", "cancelled"}
    # A second click is not an error: it answers with the run as it stands.
    assert admin.post(f"/admin/studies/{study_id}/evaluations/{run_id}/cancel").status_code == 202


# ------------------------------------------------------------------ the durable count


def test_progress_is_read_from_what_was_persisted_not_from_the_run(
    admin, open_study, patched_package, monkeypatch
):
    """The count has to answer after a restart, and for a batch someone ran from a
    terminal — which is exactly what an in-memory run cannot do."""
    study_id, _ = open_study

    before = admin.get(f"/admin/studies/{study_id}/evaluations").json()
    assert (before["courses"], before["evaluated"]) == (2, 0)
    assert before["evaluated_by_assessor"] == []
    assert before["runs"] == []
    assert before["default_concurrency"] >= 1

    monkeypatch.setattr(module, "_run_use_case", lambda run, course: uuid4())
    run_id = admin.post(
        f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package)
    ).json()["run_id"]
    finished(admin, study_id, run_id)

    after = admin.get(f"/admin/studies/{study_id}/evaluations").json()
    # Still 0: the fake use case persisted no evaluation, so no judgment was derived. The
    # count follows the database, not the run's own opinion of how it went.
    assert after["evaluated"] == 0
    assert after["evaluated_by_assessor"] == []
    assert [r["run_id"] for r in after["runs"]] == [run_id]


def test_reading_the_runs_of_another_study_never_leaks_this_ones(
    admin, cleanup, open_study, patched_package, monkeypatch
):
    monkeypatch.setattr(module, "_run_use_case", lambda run, course: uuid4())
    study_id, _ = open_study
    run_id = admin.post(
        f"/admin/studies/{study_id}/evaluations", json=start_body(patched_package)
    ).json()["run_id"]
    finished(admin, study_id, run_id)

    other = declare(admin, cleanup, purpose="Another round")
    assert admin.get(f"/admin/studies/{other}/evaluations").json()["runs"] == []
    assert admin.get(f"/admin/studies/{other}/evaluations/{run_id}").status_code == 404
