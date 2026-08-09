"""Retire `generator_artifacts` (ADR-0030).

The table held hand-typed `{kind, locator}` rows against a generator version, under the
first-increment mark "register yes, extract no". Nothing ever read it: no policy subscribed to
`GeneratorArtifactRegistered`, and its only reader was the list endpoint feeding the form that
wrote it. ADR-0030 retires the concept — the generator's internals stay with the generator,
where they can be kept true — and keeps the one thing that was wanted, an optional changelog, in
the `generator_versions.metadata` blob that already exists.

Rows are dropped, not migrated. There is nowhere to migrate them to: `metadata` holds reference
prose about a version, not locators pointing at files this system cannot fetch. The deploy is
still pending, so the only rows that can exist are local experiments.

Historical `events` rows of type `GeneratorArtifactRegistered` are untouched — a domain event is
a past fact and the outbox is append-only (ADR-0003).

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("generator_artifacts")


def downgrade() -> None:
    # The schema goes back, the data does not — same asymmetry as 0008 and 0015. Recreating the
    # shape is what makes the migration reversible for anyone stepping through revisions; it
    # cannot resurrect rows, and nothing in the code would read them if it did.
    op.create_table(
        "generator_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "generator_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("generator_versions.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("format", sa.Text()),
        sa.Column("registered_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    )
