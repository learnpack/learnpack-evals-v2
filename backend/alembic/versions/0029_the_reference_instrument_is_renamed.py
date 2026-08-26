"""The reference instrument keeps its content and gets the id it should have had (ADR-0056).

`learnpack-pedagogical-v2` becomes `learnpack-pedagogical-2.0.0`, and the row's `name` becomes
*LearnPack Pedagogical Rubric*. **The twelve items do not change** — not their ids, not their
text, not their scale. This is a re-identification, not a new version: publishing a second
version with identical content would leave the team choosing between two names for one thing.

It is available only now. The GLOSSARY makes stability a property of a published version,
frozen **from its first reference campaign** — and none has run. After the first one, this id
is answered data and renaming it would rewrite what people were asked.

`rubric_versions.id` is composed as `{rubric_id}-{version}` (08-code §9), so `version` moves
with the id or the row contradicts its own key. The seeder cannot repair that: its upsert
matches on the id, and a changed version *is* a different row to it.

The FK from `criteria` is dropped and rebuilt around the update — Postgres constraints are not
deferrable by default, so neither table can be updated first while it stands. The other four
columns that carry this id (`campaigns`, `evaluations`, `content_evaluation_completions`,
`golden_references`) declare no FK to it and are updated by value.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ID = "learnpack-pedagogical-v2"
NEW_ID = "learnpack-pedagogical-2.0.0"
OLD_VERSION = "v2"
NEW_VERSION = "2.0.0"
OLD_NAME = "LearnPack Pedagogical Reference v2"
NEW_NAME = "LearnPack Pedagogical Rubric"

# Every column holding a reference instrument version id. `criteria` is handled apart: it is
# the only one with a foreign key.
REFERRING = (
    ("campaigns", "instrument_version_id"),
    ("evaluations", "instrument_version_id"),
    ("content_evaluation_completions", "instrument_version_id"),
    ("golden_references", "instrument_version_id"),
)


def _rename(old_id: str, new_id: str, new_version: str, name: str) -> None:
    op.drop_constraint("criteria_rubric_version_id_fkey", "criteria", type_="foreignkey")
    op.execute(
        f"UPDATE rubric_versions SET id = '{new_id}', version = '{new_version}', "
        f"name = '{name}' WHERE id = '{old_id}'"
    )
    op.execute(
        f"UPDATE criteria SET rubric_version_id = '{new_id}' WHERE rubric_version_id = '{old_id}'"
    )
    op.create_foreign_key(
        "criteria_rubric_version_id_fkey",
        "criteria",
        "rubric_versions",
        ["rubric_version_id"],
        ["id"],
    )
    for table, column in REFERRING:
        op.execute(f"UPDATE {table} SET {column} = '{new_id}' WHERE {column} = '{old_id}'")


def upgrade() -> None:
    _rename(OLD_ID, NEW_ID, NEW_VERSION, NEW_NAME)


def downgrade() -> None:
    _rename(NEW_ID, OLD_ID, OLD_VERSION, OLD_NAME)
