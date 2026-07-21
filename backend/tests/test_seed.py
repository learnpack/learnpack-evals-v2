"""The seed must be re-runnable: rubric v1 is published and locked, so a second run
updates in place instead of duplicating (08-code.md §9).
"""

from sqlalchemy import text

from app.cli import DEFAULT_SEED_FILE, run_seed
from app.platform.db import SessionLocal

RUBRIC_VERSION_ID = "learnpack-pedagogical-v1"


def test_seed_is_idempotent(requires_db):
    run_seed(DEFAULT_SEED_FILE)
    run_seed(DEFAULT_SEED_FILE)

    with SessionLocal() as session:
        criteria = session.execute(
            text("SELECT count(*) FROM criteria WHERE rubric_version_id = :id"),
            {"id": RUBRIC_VERSION_ID},
        ).scalar_one()
        frameworks = session.execute(
            text("SELECT count(*) FROM pedagogical_frameworks")
        ).scalar_one()
        status = session.execute(
            text("SELECT status FROM rubric_versions WHERE id = :id"),
            {"id": RUBRIC_VERSION_ID},
        ).scalar_one()
        order = (
            session.execute(
                text(
                    "SELECT criterion_id FROM criteria WHERE rubric_version_id = :id ORDER BY ord"
                ),
                {"id": RUBRIC_VERSION_ID},
            )
            .scalars()
            .all()
        )

    assert criteria == 5
    assert frameworks == 6
    assert status == "published"
    assert order == [
        "objectives-quality",
        "constructive-alignment",
        "instructional-design",
        "inter-lesson-coherence",
        "learning-progression",
    ]


def test_metadata_schema_seeded(requires_db):
    run_seed(DEFAULT_SEED_FILE)

    with SessionLocal() as session:
        spec = session.execute(
            text("SELECT spec FROM metadata_schemas WHERE generating_system = 'LearnpackV1'")
        ).scalar_one()

    # ADR-0001: keys live in reference data, never in the domain. No lessonPlan.
    assert set(spec) == {"learningObjectives", "targetAudience", "prerequisites"}
