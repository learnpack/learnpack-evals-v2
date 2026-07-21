"""Admin CLI: `python -m app.cli seed`.

The MVP has no rubric authoring UI: `LearnPack Pedagogical Rubric v1` is seeded straight
into a `published`, locked version (07-define.md, "Realización MVP"; 08-code.md §9).

`docs/seed/rubric-v1.json` stays the single source of truth — it is not duplicated inside
/backend. The seed therefore runs locally against Neon, never from the Render container.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.identity.domain.assessor import InvalidAssessor, Role
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_FILE = REPO_ROOT / "docs" / "seed" / "rubric-v1.json"

# Content metadata is an open collection validated against this schema (ADR-0001).
# The domain never references these keys; only the schema and the UI know them.
LEARNPACK_METADATA_SCHEMA = {
    "generatingSystem": "LearnpackV1",
    "keys": {
        "learningObjectives": {"valueType": "string_list", "required": True},
        "targetAudience": {"valueType": "string", "required": True},
        "prerequisites": {"valueType": "string_list", "required": False},
    },
}


def _rubric_version_id(rubric: dict[str, Any]) -> str:
    return f"{rubric['rubricId']}-{rubric['version']}"


def seed_rubric(session: Session, rubric: dict[str, Any]) -> None:
    """Upsert frameworks + the published rubric version + its criteria. Idempotent."""
    for framework in rubric["frameworks"]:
        session.execute(
            text(
                """
                INSERT INTO pedagogical_frameworks (id, citation)
                VALUES (:id, :citation)
                ON CONFLICT (id) DO UPDATE SET citation = excluded.citation
                """
            ),
            framework,
        )

    version_id = _rubric_version_id(rubric)
    scale = rubric["scale"]
    session.execute(
        text(
            """
            INSERT INTO rubric_versions
                (id, rubric_id, version, name, status, scope, scale_min, scale_max, published_at)
            VALUES
                (:id, :rubric_id, :version, :name, :status, :scope, :scale_min, :scale_max, now())
            ON CONFLICT (id) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                scope = excluded.scope,
                scale_min = excluded.scale_min,
                scale_max = excluded.scale_max
            """
        ),
        {
            "id": version_id,
            "rubric_id": rubric["rubricId"],
            "version": rubric["version"],
            "name": rubric["name"],
            "status": rubric["status"],
            "scope": rubric["scope"],
            "scale_min": scale["min"],
            "scale_max": scale["max"],
        },
    )

    for criterion in rubric["criteria"]:
        session.execute(
            text(
                """
                INSERT INTO criteria
                    (rubric_version_id, criterion_id, ord, dimension, prompt, guidance,
                     anchor_low, anchor_high, qualities, grounded_in, eligible_sources)
                VALUES
                    (:rubric_version_id, :criterion_id, :ord, :dimension, :prompt, :guidance,
                     :anchor_low, :anchor_high, :qualities, :grounded_in, :eligible_sources)
                ON CONFLICT (rubric_version_id, criterion_id) DO UPDATE SET
                    ord = excluded.ord,
                    dimension = excluded.dimension,
                    prompt = excluded.prompt,
                    guidance = excluded.guidance,
                    anchor_low = excluded.anchor_low,
                    anchor_high = excluded.anchor_high,
                    qualities = excluded.qualities,
                    grounded_in = excluded.grounded_in,
                    eligible_sources = excluded.eligible_sources
                """
            ),
            {
                "rubric_version_id": version_id,
                "criterion_id": criterion["criterionId"],
                "ord": criterion["order"],
                "dimension": criterion["dimension"],
                "prompt": criterion["prompt"],
                "guidance": criterion["guidance"],
                "anchor_low": criterion.get("anchorLow", scale["anchorLow"]),
                "anchor_high": criterion.get("anchorHigh", scale["anchorHigh"]),
                "qualities": json.dumps(criterion["qualities"]),
                "grounded_in": json.dumps(criterion["groundedIn"]),
                "eligible_sources": json.dumps(criterion["eligibleSources"]),
            },
        )


def seed_metadata_schema(session: Session) -> None:
    session.execute(
        text(
            """
            INSERT INTO metadata_schemas (generating_system, spec)
            VALUES (:generating_system, :spec)
            ON CONFLICT (generating_system) DO UPDATE SET spec = excluded.spec
            """
        ),
        {
            "generating_system": LEARNPACK_METADATA_SCHEMA["generatingSystem"],
            "spec": json.dumps(LEARNPACK_METADATA_SCHEMA["keys"]),
        },
    )


def run_seed(seed_file: Path) -> None:
    rubric = json.loads(seed_file.read_text(encoding="utf-8"))
    with SessionLocal() as session:
        seed_rubric(session, rubric)
        seed_metadata_schema(session)
        session.commit()

        criteria_count = session.execute(
            text("SELECT count(*) FROM criteria WHERE rubric_version_id = :id"),
            {"id": _rubric_version_id(rubric)},
        ).scalar_one()
        frameworks_count = session.execute(
            text("SELECT count(*) FROM pedagogical_frameworks")
        ).scalar_one()

    print(
        f"seeded {rubric['name']} ({_rubric_version_id(rubric)}): "
        f"{criteria_count} criteria, {frameworks_count} frameworks, 1 metadata schema"
    )


def run_set_role(email: str, role: str) -> int:
    """Promote/demote an Assessor.

    `assessors.role` is the source of truth for authorisation, and only this command writes
    it — logging in never changes a role, so authentication cannot escalate privileges.
    """
    with SessionLocal() as session:
        repository = SqlAlchemyAssessorRepository(session)
        assessor = repository.get_by_email(email)
        if assessor is None:
            print(
                f"no assessor with email {email!r}. "
                "They must sign in once before a role can be assigned.",
                file=sys.stderr,
            )
            return 1
        try:
            assessor.assign_role(role)
        except InvalidAssessor as exc:
            print(str(exc), file=sys.stderr)
            return 1
        repository.update(assessor)
        session.commit()

    print(f"{email} is now {role}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    seed_parser = subparsers.add_parser("seed", help="seed rubric v1 + metadata schema")
    seed_parser.add_argument("--file", type=Path, default=DEFAULT_SEED_FILE)

    role_parser = subparsers.add_parser("set-role", help="assign a role to an assessor")
    role_parser.add_argument("--email", required=True)
    role_parser.add_argument("--role", required=True, choices=[r.value for r in Role])

    args = parser.parse_args(argv)

    if args.command == "seed":
        if not args.file.exists():
            print(f"seed file not found: {args.file}", file=sys.stderr)
            return 1
        run_seed(args.file)
    elif args.command == "set-role":
        return run_set_role(args.email, args.role)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
