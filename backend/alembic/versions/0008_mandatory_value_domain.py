"""Make `data_requirements.value_domain` mandatory — the declared shape of each datum.

Realizes ADR-0020 (refines ADR-0014): the definition says what a datum MEANS, the value
domain says what shape it TAKES. Until now the shape lived only in the prose of the
definition, so nothing could check that what an extraction adapter produced actually had
it — and an assessor reading a mis-shaped value can emit a cited `fail` for a defect that
does not exist.

Rows without a value domain are deleted rather than backfilled: a requirement whose shape
is undeclared is, by ADR-0020, not a valid data requirement. The namespace is re-created
by `python -m app.cli import-instrument --file docs/seed/instruments/<instrument>.yaml`,
which is where the value domains are authored. Safe in this phase for the reason 13-code
§2 already gave for the rubric/evaluation tables: the data is experimental, no study has
pinned an instrument version yet, and the YAML is the source the rows come from. No FK
points here — criteria reference requirement ids inside a jsonb column.

This also retires the orphan `practice_exercises` row left behind by an earlier draft of
the first instrument (the import never deletes).

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM data_requirements WHERE value_domain IS NULL")
    op.alter_column(
        "data_requirements",
        "value_domain",
        existing_type=postgresql.JSONB(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "data_requirements",
        "value_domain",
        existing_type=postgresql.JSONB(),
        nullable=True,
    )
