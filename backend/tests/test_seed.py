"""The seed must be re-runnable: the reference instrument is published and locked, so a
second run updates in place instead of duplicating (08-code.md §9).
"""

import json

from sqlalchemy import text

from app.cli import (
    DEFAULT_SEED_FILE,
    DEMO_INSTRUMENT_SPEC,
    _import_demo_instrument,
    _instrument_identity,
    _reset_demo,
    run_import_instrument,
    run_seed,
)
from app.modules.identity.domain.assessor import Assessor
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from app.shared.domain.ids import new_id

RUBRIC_VERSION_ID = "learnpack-pedagogical-2.0.0"


def test_seed_is_idempotent(requires_db):
    run_seed(DEFAULT_SEED_FILE)
    run_seed(DEFAULT_SEED_FILE)

    with SessionLocal() as session:
        item_count = session.execute(
            text("SELECT count(*) FROM rubric_items WHERE rubric_version_id = :id"),
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
                    "SELECT quality_id FROM rubric_items WHERE rubric_version_id = :id ORDER BY ord"
                ),
                {"id": RUBRIC_VERSION_ID},
            )
            .scalars()
            .all()
        )
        response_format = session.execute(
            text("SELECT response_format FROM rubric_versions WHERE id = :id"),
            {"id": RUBRIC_VERSION_ID},
        ).scalar_one()

    assert item_count == 12
    assert frameworks == 6
    assert status == "published"
    assert response_format == "likert"
    # One item per Quality, and the item's id IS the quality id — the join ADR-0015 §4 needs
    # is the primary key, not a lookup (ADR-0052 §1).
    assert order == [
        "objectives-observable",
        "progression-starting-point",
        "alignment-coverage",
        "alignment-assessment",
        "instruction-authentic-problems",
        "instruction-demonstration",
        "instruction-prior-knowledge",
        "coherence-logical-sequence",
        "coherence-reinforcement",
        "coherence-explicit-links",
        "progression-prerequisites",
        "progression-cognitive-demand",
    ]


def test_reference_data_seeded(requires_db):
    """Dimensions and qualities are the stable column of the language, and since ADR-0052
    the reference panel elicits one item per quality rather than one per dimension — so the
    twelve items above are a subset of these ids, not a parallel vocabulary."""
    run_seed(DEFAULT_SEED_FILE)
    run_seed(DEFAULT_SEED_FILE)  # idempotent

    with SessionLocal() as session:
        dimensions = session.execute(
            text("SELECT count(*) FROM pedagogical_dimensions")
        ).scalar_one()
        qualities = session.execute(text("SELECT count(*) FROM qualities")).scalar_one()
        undefined = session.execute(
            text("SELECT count(*) FROM qualities WHERE definition = ''")
        ).scalar_one()
        named_frameworks = session.execute(
            text("SELECT count(*) FROM pedagogical_frameworks WHERE name IS NOT NULL")
        ).scalar_one()
        orphan_qualities = session.execute(
            text(
                "SELECT count(*) FROM qualities q LEFT JOIN pedagogical_dimensions d "
                "ON q.dimension_id = d.id WHERE d.id IS NULL"
            )
        ).scalar_one()

    assert dimensions == 5
    assert qualities == 21
    assert undefined == 0
    assert named_frameworks == 6
    assert orphan_qualities == 0


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
            auth_provider="local",
            auth_subject=f"stale-{unique}@local.test",
            email=f"stale-{unique}@local.test",
        )
        clerk_user = Assessor(
            id=new_id(),
            auth_provider="clerk",
            auth_subject=f"user_{unique}",
            email=f"real-{unique}@example.com",
        )
        repository.add(local_user)
        repository.add(clerk_user)
        session.commit()
        cleanup["assessors"].append(clerk_user.id)

        _reset_demo(session)

        assert repository.get_by_credential("local", local_user.auth_subject) is None
        assert repository.get_by_credential("clerk", clerk_user.auth_subject) is not None


def test_reset_demo_clears_the_automated_assessor_registration(requires_db, cleanup, unique):
    """An automated assessor is app-minted, not seeded reference data, so the reset must
    reach it.

    Leaving one behind strands its stored `source_config`. The next `ratify-assessor`
    then refuses with "the artifact changed without a version bump" (ADR-0016) — a correct
    guard, fired on a database the operator was just told had been reset, and pointing at
    the code rather than at the stale row.
    """
    with SessionLocal() as session:
        session.execute(
            text(
                "INSERT INTO assessors (id, kind, source_config, role, created_at) "
                "VALUES (:id, 'automated', :config, 'evaluator', now())"
            ),
            {
                "id": str(new_id()),
                "config": json.dumps({"name": f"stale-{unique}", "version": "1"}),
            },
        )
        session.commit()

        _reset_demo(session)

        assert (
            session.execute(
                text("SELECT count(*) FROM assessors WHERE kind = 'automated'")
            ).scalar_one()
            == 0
        )


def test_seed_demo_leaves_a_published_instrument_alone(requires_db, cleanup, capsys):
    """The workbench publishes learnpack-course-qa-v1; re-importing over a published
    version is refused (ADR-0012). seed-demo must treat that as the idempotent branch,
    the same way seed-workbench does, rather than aborting the rest of the demo.
    """
    _, version_id = _instrument_identity(DEMO_INSTRUMENT_SPEC)
    cleanup["instruments"].append(version_id)
    assert run_import_instrument(DEMO_INSTRUMENT_SPEC) == 0

    with SessionLocal() as session:
        session.execute(
            text("UPDATE instrument_versions SET status = 'published' WHERE id = :id"),
            {"id": version_id},
        )
        session.commit()

    capsys.readouterr()
    assert _import_demo_instrument() == 0
    assert f"instrument {version_id} is already published" in capsys.readouterr().out

    with SessionLocal() as session:
        status = session.execute(
            text("SELECT status FROM instrument_versions WHERE id = :id"),
            {"id": version_id},
        ).scalar_one()
    assert status == "published"
