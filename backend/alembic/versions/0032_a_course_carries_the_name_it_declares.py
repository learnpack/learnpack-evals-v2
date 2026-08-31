"""A course keeps the title its package declares (ADR-0059).

Discovery has always read it — `learn.json`'s title, the lesson plan's `course_title` — and
the registration dropped it on the floor. The column is where it lands now, beside the other
things discovery read about the course: its external id, its version, the hash of its bytes.

Nullable, and null is a true statement: this course was registered before the title was kept,
or its package declares none. Nothing is backfilled here — the honest value for an existing
row lives in that course's profile, and reading another module's table from a registry
migration is not how it gets here. `backfill-content-titles` does it, once, and can be run
again for a course profiled later.

Revision ID: 0032
Revises: 0031
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("title", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "title")
