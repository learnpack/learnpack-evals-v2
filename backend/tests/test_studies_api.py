"""The study lifecycle over the admin API (13-code §3.6/§6).

Domain invariants are specified in test_studies_domain.py; here the HTTP mapping:
404/409/422 per act, the readiness/matching composed queries, and the report row.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text
from test_instrument_authoring_api import import_spec, spec

SYLLABUS_URL = "https://packages.learn-pack.com"


@pytest.fixture
def admin_client(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


def published_instrument(admin_client, cleanup, unique) -> str:
    instrument_id = import_spec(cleanup, spec(unique))
    response = admin_client.post(f"/admin/instruments/{instrument_id}/publish")
    assert response.status_code == 200, response.text
    return instrument_id


def declare(admin_client, cleanup, purpose="A test round") -> str:
    response = admin_client.post("/admin/studies", json={"purpose": purpose})
    assert response.status_code == 201, response.text
    study_id = response.json()["study_id"]
    cleanup["studies"].append(study_id)
    return study_id


def register_brief(admin_client, cleanup, text="Create a course about tests.") -> str:
    response = admin_client.post("/admin/briefs", json={"brief": text, "fields": {}})
    assert response.status_code == 201, response.text
    brief_id = response.json()["brief_id"]
    cleanup["briefs"].append(brief_id)
    return brief_id


def register_content(admin_client, cleanup, unique, suffix, brief_id=None) -> str:
    response = admin_client.post(
        "/admin/contents",
        json={
            "package_format": "LearnpackV1",
            "external_id": f"study-api-{suffix}-{unique}",
            "consumable_url": f"{SYLLABUS_URL}/{suffix}-{unique}/",
            "generator_version_id": None,
            "brief_id": brief_id,
        },
    )
    assert response.status_code == 201, response.text
    content_id = response.json()["content_id"]
    cleanup["contents"].append(content_id)
    return content_id


def composed_study(admin_client, cleanup, unique):
    """declared → pinned → composed, ready to open."""
    instrument_id = published_instrument(admin_client, cleanup, unique)
    study_id = declare(admin_client, cleanup)
    brief_id = register_brief(admin_client, cleanup)
    register_content(admin_client, cleanup, unique, "a", brief_id)
    admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": instrument_id}
    )
    admin_client.post(f"/admin/studies/{study_id}/dataset", json={"brief_ids": [brief_id]})
    return study_id, instrument_id, brief_id


def test_the_full_lifecycle_over_the_api(admin_client, cleanup, unique):
    study_id, instrument_id, brief_id = composed_study(admin_client, cleanup, unique)

    body = admin_client.get(f"/admin/studies/{study_id}").json()
    assert body["status"] == "prepared"
    assert body["instrument_version_id"] == instrument_id
    assert body["brief_ids"] == [brief_id]
    assert len(body["content_ids"]) == 1

    # No report before publishing.
    assert admin_client.get(f"/admin/studies/{study_id}/report").status_code == 404

    assert admin_client.post(f"/admin/studies/{study_id}/open").status_code == 200
    assert admin_client.get(f"/admin/studies/{study_id}").json()["status"] == "open"

    response = admin_client.post(f"/admin/studies/{study_id}/publish")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"

    report = admin_client.get(f"/admin/studies/{study_id}/report").json()["report"]
    assert report["studyId"] == study_id
    assert report["instrumentVersionId"] == instrument_id
    # Nothing evaluated yet: the report says so instead of publishing silently.
    assert report["judgmentIdsUsed"] == {}
    assert body["content_ids"] == report["caveats"]["contentsWithoutJudgment"]
    assert report["caveats"]["unknownExclusions"]["contentIds"] == body["content_ids"]

    # Published is immutable — every later act conflicts.
    assert admin_client.post(f"/admin/studies/{study_id}/publish").status_code == 409
    assert admin_client.post(f"/admin/studies/{study_id}/open").status_code == 409
    assert (
        admin_client.post(f"/admin/studies/{study_id}/dataset", json={"brief_ids": []})
    ).status_code == 409

    listed = admin_client.get("/admin/studies").json()
    assert study_id in {s["study_id"] for s in listed}


def test_the_list_answers_newest_first_and_carries_the_date_it_sorts_on(
    admin_client, cleanup, unique
):
    """The console reads this list from the top, so the study just declared has to be there.

    Relative positions rather than absolute ones: the database is shared with whatever else
    the suite declared. And the date it sorts on travels with every row, so a reader can
    check the order instead of trusting it.
    """
    older = declare(admin_client, cleanup, purpose=f"older round {unique}")
    newer = declare(admin_client, cleanup, purpose=f"newer round {unique}")

    response = admin_client.get("/admin/studies")
    assert response.status_code == 200, response.text
    listed = response.json()

    ids = [study["study_id"] for study in listed]
    assert ids.index(newer) < ids.index(older), ids
    assert all(study["created_at"] for study in listed), response.text


def test_pin_is_once_and_only_published_versions(admin_client, cleanup, unique):
    study_id = declare(admin_client, cleanup)

    unknown = admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": "ghost-v1"}
    )
    assert unknown.status_code == 422

    draft_id = import_spec(cleanup, spec(unique))
    draft = admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": draft_id}
    )
    assert draft.status_code == 422
    assert "publish it before pinning" in draft.json()["detail"]

    admin_client.post(f"/admin/instruments/{draft_id}/publish")
    assert (
        admin_client.post(
            f"/admin/studies/{study_id}/pin", json={"instrument_version_id": draft_id}
        ).status_code
        == 200
    )
    again = admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": draft_id}
    )
    assert again.status_code == 409  # pinned ONCE


def test_open_preconditions_map_to_422(admin_client, cleanup, unique):
    study_id = declare(admin_client, cleanup)
    assert admin_client.post(f"/admin/studies/{study_id}/open").status_code == 422  # no pin

    instrument_id = published_instrument(admin_client, cleanup, unique)
    admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": instrument_id}
    )
    empty = admin_client.post(f"/admin/studies/{study_id}/open")
    assert empty.status_code == 422  # empty dataset

    assert admin_client.post(f"/admin/studies/{study_id}/publish").status_code == 409  # not open


def test_unknown_briefs_and_studies_are_named(admin_client, cleanup, unique):
    assert admin_client.get("/admin/studies/00000000-0000-0000-0000-000000000000").status_code == (
        404
    )
    study_id = declare(admin_client, cleanup)
    response = admin_client.post(
        f"/admin/studies/{study_id}/dataset",
        json={"brief_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert response.status_code == 422


def test_readiness_informs_and_never_blocks(admin_client, cleanup, unique):
    study_id = declare(admin_client, cleanup)

    fresh = admin_client.get(f"/admin/studies/{study_id}/readiness").json()
    assert fresh["informative"] is True
    gaps = {g["gap"] for g in fresh["studyGaps"]}
    assert gaps == {"instrument_not_pinned", "dataset_not_composed"}

    instrument_id = published_instrument(admin_client, cleanup, unique)
    admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": instrument_id}
    )
    pinned = admin_client.get(f"/admin/studies/{study_id}/readiness").json()
    gaps = {g["gap"] for g in pinned["studyGaps"]}
    # ADR-0019: nobody is ratified for this fresh version — readiness says so, loudly.
    assert "no_ratified_assessor" in gaps
    assert "instrument_not_pinned" not in gaps

    # The gap report is per claim once the instrument is known.
    assert {c["claimId"] for c in pinned["claims"]} == {"cl-objectives"}


def test_fitness_is_its_own_resource_and_informs_before_there_is_anything_to_measure(
    admin_client, cleanup, unique
):
    """ADR-0023: an optimization signal, on its own endpoint — never inside the report,
    whose jsonb is frozen and whose coverage uses a different denominator."""
    study_id = declare(admin_client, cleanup)

    fresh = admin_client.get(f"/admin/studies/{study_id}/fitness")
    assert fresh.status_code == 200, fresh.text
    body = fresh.json()
    assert body["signal"] == "optimization"
    assert body["formulaVersion"]
    # It answers with its gaps instead of refusing, the way readiness informs.
    assert {g["gap"] for g in body["gaps"]} == {"instrument_not_pinned", "dataset_not_composed"}
    assert body["study"] == {}

    instrument_id = published_instrument(admin_client, cleanup, unique)
    admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": instrument_id}
    )
    pinned = admin_client.get(f"/admin/studies/{study_id}/fitness").json()
    # The instrument's qualities are known even before a single content is judged, and each
    # is undefined rather than zero — nothing was measurable yet.
    assert pinned["study"]["qualities"]["objectives-observable"]["fitness"] is None
    assert pinned["denominatorRule"]["excluded"] == [
        "not_applicable",
        "not_assessed",
        "execution_error",
    ]

    assert admin_client.get(f"/admin/studies/{uuid4()}/fitness").status_code == 404


def test_the_preview_answers_before_publishing_and_never_says_it_was_published(
    admin_client, cleanup, unique
):
    """The whole reason this resource exists: a report that appears only after an
    irreversible act is a report nobody can read before committing to it.

    Pinned here: it answers while the study is still being set up and once it is composed;
    the frozen `/report` keeps its 404 beside it; and `publishedAt` is absent, because a
    preview carrying the composition's clock renders as "Published now".
    """
    bare_id = declare(admin_client, cleanup)

    fresh = admin_client.get(f"/admin/studies/{bare_id}/report/preview")
    assert fresh.status_code == 200, fresh.text
    body = fresh.json()
    assert body["documentKind"] == "preview", fresh.text
    assert "publishedAt" not in body, fresh.text
    assert body["composedAt"], fresh.text
    assert body["frozenRecord"]["exists"] is False, fresh.text
    assert {g["gap"] for g in body["gaps"]} == {"instrument_not_pinned", "dataset_not_composed"}
    # Never a partial document: the empty sections are there, and every caveat kind.
    assert body["contents"] == [] and body["generatorLevel"] == []
    assert "insufficientEvidence" in body["caveats"], fresh.text

    study_id, instrument_id, _ = composed_study(admin_client, cleanup, unique)
    prepared = admin_client.get(f"/admin/studies/{study_id}/report/preview")
    assert prepared.status_code == 200, prepared.text
    composed = prepared.json()
    assert composed["gaps"] == [], prepared.text
    assert composed["instrumentVersionId"] == instrument_id
    assert "publishedAt" not in composed, prepared.text
    assert len(composed["contents"]) == 1, prepared.text
    # Previewing is not publishing: the frozen row still does not exist.
    assert admin_client.get(f"/admin/studies/{study_id}/report").status_code == 404


def test_previewing_publishes_no_event_and_persists_nothing(admin_client, cleanup, unique, session):
    """A preview is a read. If it ever became a write, this is where it shows: the study
    would leave `prepared`, `study_reports` would gain a row, and the outbox would gain a
    `StudyPublished` nobody performed."""
    study_id, _, _ = composed_study(admin_client, cleanup, unique)

    before = session.execute(
        text("SELECT count(*) FROM events WHERE aggregate_id = :id"), {"id": study_id}
    ).scalar_one()

    assert admin_client.get(f"/admin/studies/{study_id}/report/preview").status_code == 200
    assert admin_client.get(f"/admin/studies/{study_id}/report/preview").status_code == 200

    after = session.execute(
        text("SELECT count(*) FROM events WHERE aggregate_id = :id"), {"id": study_id}
    ).scalar_one()
    assert after == before
    assert admin_client.get(f"/admin/studies/{study_id}").json()["status"] == "prepared"
    assert admin_client.get(f"/admin/studies/{study_id}/report").status_code == 404


def test_the_criterion_matrix_is_its_own_resource_and_has_a_denominator_from_the_pin(
    admin_client, cleanup, unique
):
    """ADR-0011: a count of failures with no denominator is not an answer. The criteria come
    from the instrument, so each has a denominator the moment a version is pinned — before
    a single course has been judged."""
    study_id = declare(admin_client, cleanup)

    fresh = admin_client.get(f"/admin/studies/{study_id}/criterion-outcomes")
    assert fresh.status_code == 200, fresh.text
    body = fresh.json()
    assert body["signal"] == "evidence", fresh.text
    assert {g["gap"] for g in body["gaps"]} == {"instrument_not_pinned", "dataset_not_composed"}
    assert body["criteria"] == [] and body["contents"] == []

    instrument_id = published_instrument(admin_client, cleanup, unique)
    admin_client.post(
        f"/admin/studies/{study_id}/pin", json={"instrument_version_id": instrument_id}
    )
    pinned = admin_client.get(f"/admin/studies/{study_id}/criterion-outcomes").json()
    assert [c["criterionId"] for c in pinned["criteria"]] == ["cr-min-objectives"]
    # A criterion nothing produced an outcome for is 0 of 0, never a missing row.
    assert pinned["criteria"][0]["coverage"] == {"observed": 0, "of": 0}
    assert pinned["judgmentBasis"]["basis"] == "current"


def test_an_unknown_study_has_neither_a_preview_nor_a_matrix(admin_client):
    """Composed on read is not invented on read: there is no study to compose from."""
    ghost = uuid4()
    assert admin_client.get(f"/admin/studies/{ghost}/report/preview").status_code == 404
    assert admin_client.get(f"/admin/studies/{ghost}/criterion-outcomes").status_code == 404


def test_matching_reports_the_unmet_demand_per_format(admin_client, cleanup, unique):
    instrument_id = published_instrument(admin_client, cleanup, unique)

    response = admin_client.get(
        f"/admin/instruments/{instrument_id}/matching?package_format=LearnpackV1"
    )
    assert response.status_code == 200, response.text
    matching = response.json()

    # The test instrument demands objectives_<unique>, which no LearnpackV1 adapter
    # supplies — the ADR-0017 systemic gap, stated once at the matching level.
    assert matching["unmetDemand"] == [
        {"dataRequirementId": f"objectives_{unique}", "criterionIds": ["cr-min-objectives"]}
    ]
    assert matching["claims"] == [{"claimId": "cl-objectives", "criteria": 1, "coveredCriteria": 0}]

    missing = admin_client.get("/admin/instruments/ghost-v1/matching?package_format=LearnpackV1")
    assert missing.status_code == 404


def test_studies_require_the_admin_role(as_user, cleanup, unique):
    client = as_user(f"user_eval_{unique}", f"eval-{unique}@example.com", "Eval")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])

    assert client.get("/admin/studies").status_code == 403
    assert client.post("/admin/studies", json={"purpose": "nope"}).status_code == 403
    assert client.get(f"/admin/studies/{uuid4()}/fitness").status_code == 403
    assert client.get(f"/admin/studies/{uuid4()}/report/preview").status_code == 403
    assert client.get(f"/admin/studies/{uuid4()}/criterion-outcomes").status_code == 403
