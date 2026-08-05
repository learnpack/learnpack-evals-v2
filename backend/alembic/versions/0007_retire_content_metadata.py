"""Retire content metadata — the declared surface of the evaluand is the package.

Realizes ADR-0017 (supersedes ADR-0001): the registry-level metadata channel predates the
`ContentPackage` and, with no mechanical supplier, could only be written by hand — which
contaminated the declared surface the instrument evaluates. Everything the platform or
generator declares now travels as package artifacts and is read by the extraction adapter.
Drops `contents.metadata`, the `metadata_schemas` reference table and the campaigns'
`metadata_view` (the human evaluators' context panel — its only remaining consumer).

Existing rows lose hand-authored values by design: they were never the course declaring.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("contents", "metadata")
    op.drop_table("metadata_schemas")
    op.drop_column("campaigns", "metadata_view")


def downgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "metadata_view",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_table(
        "metadata_schemas",
        sa.Column("package_format", sa.Text(), primary_key=True),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
    )
    op.add_column(
        "contents",
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
