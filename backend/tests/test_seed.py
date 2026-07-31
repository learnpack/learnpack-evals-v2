"""The seed must be re-runnable: rubric v1 is published and locked, so a second run
updates in place instead of duplicating (08-code.md §9).
"""

from sqlalchemy import text

from app.cli import DEFAULT_SEED_FILE, _reset_demo, run_seed
from app.modules.identity.domain.assessor import Assessor
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from app.shared.domain.ids import new_id

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


def test_reset_demo_clears_local_identities_and_spares_the_rest(requires_db, cleanup, unique):
    """`seed-demo --reset` wipes local data, but never a real Clerk identity.

    Local users are matched by their `local|` prefix rather than by the demo email list:
    identities also appear by signing in with any `X-Dev-User`, and the demo emails have
    changed once already — matching the list strands those rows where no reset can reach them.

    (This wipes the local dataset of whatever database the suite runs against. Safe here
    because every test creates the data it needs.)
    """
    with SessionLocal() as session:
        repository = SqlAlchemyAssessorRepository(session)
        local_user = Assessor(
            id=new_id(),
            clerk_user_id=f"local|stale-{unique}@local.test",
            email=f"stale-{unique}@local.test",
        )
        clerk_user = Assessor(
            id=new_id(),
            clerk_user_id=f"user_{unique}",
            email=f"real-{unique}@example.com",
        )
        repository.add(local_user)
        repository.add(clerk_user)
        session.commit()
        cleanup["assessors"].append(clerk_user.id)

        _reset_demo(session)

        assert repository.get_by_clerk_user_id(local_user.clerk_user_id) is None
        assert repository.get_by_clerk_user_id(clerk_user.clerk_user_id) is not None
