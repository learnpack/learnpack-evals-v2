"""Instrument authoring end to end: import a draft, publish it, read the snapshot.

Import is file/CLI-based (no authoring UI); publishing is the human act, exposed both as
CLI and admin endpoint. The reference data (qualities, frameworks) comes from the seed.
"""

import pytest
from sqlalchemy import text

from app.modules.evaluation_design.application.import_instrument_draft import (
    ImportInstrumentDraft,
    ImportInstrumentDraftCommand,
    InstrumentImportError,
)
from app.modules.evaluation_design.domain.instrument import InstrumentImmutable
from app.modules.evaluation_design.domain.reference import DataRequirement
from app.modules.evaluation_design.infrastructure.repository import (
    SqlAlchemyDataRequirementRepository,
    SqlAlchemyInstrumentRepository,
)
from app.platform.db import SessionLocal
from app.platform.uow import UnitOfWork


@pytest.fixture
def admin_client(as_user, cleanup, promote, unique):
    email = f"admin-{unique}@example.com"
    client = as_user(f"user_admin_{unique}", email, "Admin")
    cleanup["assessors"].append(client.get("/me").json()["assessor_id"])
    promote(email)
    return client


def spec(unique: str, **overrides) -> dict:
    base = {
        "instrument_id": f"qa-{unique}",
        "version": "v1",
        "name": "Course QA (test)",
        "purpose": "internal QA of generated courses",
        "assisted_by": {"assistant": "test-suite"},
        "bindings": [{"package_format": "LearnpackV1"}],
        "data_requirements": [
            {
                "id": f"objectives_{unique}",
                "definition": "Learning objectives declared by the content.",
            }
        ],
        "claims": [
            {
                "id": "cl-objectives",
                "statement": "The course declares observable learning objectives.",
                "qualities": ["objectives-observable"],
                "warrants": ["Biggs"],
                "alternative_explanations": [
                    "objectives live in the lesson body but not in the manifest"
                ],
            }
        ],
        "criteria": [
            {
                "id": "cr-min-objectives",
                "pass_condition": "At least 2 learning objectives are declared.",
                "failure_modes": ["fewer than 2 objectives declared"],
                "claims": ["cl-objectives"],
                "requires": [f"objectives_{unique}"],
                "on_missing_evidence": "fail",
            }
        ],
    }
    return base | overrides


def import_spec(cleanup, payload: dict) -> str:
    with SessionLocal() as session:
        uow = UnitOfWork(session)
        use_case = ImportInstrumentDraft(
            instruments=SqlAlchemyInstrumentRepository(session),
            data_requirements=SqlAlchemyDataRequirementRepository(session),
            uow=uow,
        )
        result = use_case(ImportInstrumentDraftCommand(spec=payload))
    instrument_id = result.instrument.id
    if instrument_id not in cleanup["instruments"]:
        cleanup["instruments"].append(instrument_id)
    for requirement in payload.get("data_requirements", []):
        if requirement["id"] not in cleanup["data_requirements"]:
            cleanup["data_requirements"].append(requirement["id"])
    return instrument_id


def test_import_creates_a_draft_and_reimport_replaces_it(admin_client, cleanup, unique):
    instrument_id = import_spec(cleanup, spec(unique))

    body = admin_client.get(f"/admin/instruments/{instrument_id}").json()
    assert body["status"] == "draft"
    assert [c["claim_id"] for c in body["claims"]] == ["cl-objectives"]

    # Re-import with an extra criterion: the draft is replaced, not duplicated.
    updated = spec(unique)
    updated["criteria"].append(
        {
            "id": "cr-verbs",
            "pass_condition": "Every objective uses an observable action verb.",
            "failure_modes": ["objective phrased with 'understand' or 'know'"],
            "claims": ["cl-objectives"],
            "requires": [f"objectives_{unique}"],
        }
    )
    import_spec(cleanup, updated)

    body = admin_client.get(f"/admin/instruments/{instrument_id}").json()
    assert [c["criterion_id"] for c in body["criteria"]] == ["cr-min-objectives", "cr-verbs"]


def test_import_lints_conflicting_data_requirement_definitions(cleanup, unique, session):
    requirement_id = f"objectives_{unique}"
    SqlAlchemyDataRequirementRepository(session).upsert(
        DataRequirement(id=requirement_id, definition="Something else entirely.")
    )
    session.commit()
    cleanup["data_requirements"].append(requirement_id)

    with pytest.raises(InstrumentImportError, match="different\\s+definition"):
        import_spec(cleanup, spec(unique))


def test_import_rejects_undefined_required_data(cleanup, unique):
    broken = spec(unique)
    broken["criteria"][0]["requires"] = ["never_minted"]
    with pytest.raises(InstrumentImportError, match="never_minted"):
        import_spec(cleanup, broken)


def test_publish_emits_the_snapshot_and_locks_the_version(admin_client, cleanup, unique, session):
    instrument_id = import_spec(cleanup, spec(unique))

    response = admin_client.post(f"/admin/instruments/{instrument_id}/publish")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"

    payload = session.execute(
        text("SELECT payload FROM events WHERE aggregate_id = :id AND event_type = :t"),
        {"id": instrument_id, "t": "InstrumentVersionPublished"},
    ).scalar_one()
    assert payload["instrumentVersionId"] == instrument_id
    assert [c["claimId"] for c in payload["claims"]] == ["cl-objectives"]
    assert payload["criteria"][0]["passCondition"].startswith("At least 2")

    # Published means locked: publishing again and re-importing both fail.
    assert admin_client.post(f"/admin/instruments/{instrument_id}/publish").status_code == 409
    with pytest.raises(InstrumentImmutable, match="bump the version"):
        import_spec(cleanup, spec(unique))


def test_publish_rejects_an_invalid_argument(admin_client, cleanup, unique):
    ghostly = spec(unique)
    ghostly["claims"][0]["qualities"] = ["ghost-quality"]
    instrument_id = import_spec(cleanup, ghostly)

    response = admin_client.post(f"/admin/instruments/{instrument_id}/publish")
    assert response.status_code == 422
    assert "ghost-quality" in response.json()["detail"]

    # Still a draft: the failed publish changed nothing.
    assert admin_client.get(f"/admin/instruments/{instrument_id}").json()["status"] == "draft"


def test_instruments_are_listed(admin_client, cleanup, unique):
    instrument_id = import_spec(cleanup, spec(unique))
    listed = admin_client.get("/admin/instruments").json()
    assert instrument_id in {i["instrument_version_id"] for i in listed}


# ---------------------------------------------------------------- the real draft


def test_the_real_draft_imports_clean_and_would_publish(admin_client, cleanup, unique):
    """docs/seed/instruments/learnpack-course-qa-v1.yaml is data under review: it must
    import clean, and a copy must pass every publish invariant — while the real one
    STAYS a draft (publishing it is the team's human act, design 12 inv. 5)."""
    import yaml

    from app.cli import REPO_ROOT

    real_file = REPO_ROOT / "docs" / "seed" / "instruments" / "learnpack-course-qa-v1.yaml"
    real_spec = yaml.safe_load(real_file.read_text(encoding="utf-8"))

    real_id = import_spec(cleanup, real_spec)
    body = admin_client.get(f"/admin/instruments/{real_id}").json()
    assert body["status"] == "draft"
    assert len(body["claims"]) == 5
    assert len(body["criteria"]) == 10
    assert {c["claim_id"] for c in body["claims"]} == {
        "cl-objectives-declared",
        "cl-audience-declared",
        "cl-lessons-offer-application",
        "cl-course-modular",
        "cl-course-arc",
    }

    # A copy under a throwaway id proves the content satisfies the publish invariants.
    copy = dict(real_spec)
    copy["instrument_id"] = f"qa-copy-{unique}"
    copy_id = import_spec(cleanup, copy)
    published = admin_client.post(f"/admin/instruments/{copy_id}/publish")
    assert published.status_code == 200, published.text

    # The real draft was not published by any of this.
    assert admin_client.get(f"/admin/instruments/{real_id}").json()["status"] == "draft"
