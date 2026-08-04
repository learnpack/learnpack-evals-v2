"""Rename rubric_version_id to instrument_version_id in shared tables.

Glossary alignment (docs/GLOSSARY.md, ADR-0015/0016, 13-code-qa.md §2): these
columns will hold ids of new instruments OR of Rubric v1 — Rubric v1's id IS an
instrument version id. The FKs to rubric_versions are dropped (a column cannot
reference two tables); referential validation moves to the application, the
accepted pattern for cross-module references. `rubric_versions` and `criteria`
keep their names and columns: they store Rubric v1, the reference instrument.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("evaluations", "campaigns", "content_evaluation_completions", "golden_references")


def upgrade() -> None:
    for table in TABLES:
        op.drop_constraint(f"{table}_rubric_version_id_fkey", table, type_="foreignkey")
        op.alter_column(table, "rubric_version_id", new_column_name="instrument_version_id")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(table, "instrument_version_id", new_column_name="rubric_version_id")
        op.create_foreign_key(
            f"{table}_rubric_version_id_fkey",
            table,
            "rubric_versions",
            ["rubric_version_id"],
            ["id"],
        )
