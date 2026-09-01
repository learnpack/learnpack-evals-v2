"""An evaluator reaches the course's AI through a seat we hold for them (ADR-0061).

The evaluation screen embeds the course, and inside that iframe the AI is off: LearnPack
asks for a session before it will grade an open question or run an exercise, and the service
behind it resolves the token to a real person. A shared or anonymous credential is refused
there, so the AI cannot be switched on for everybody at once — it is switched on per human.

A seat is that person's credential **somewhere else**: an identity we create and hold, which
the evaluator never sees and never signs into. It is deliberately not their own account on
that platform, because binding a real address would put one human in two tenants at once and
make which one answers a matter of row order.

`(provider, external_subject)` rather than a column named after the vendor — the same shape
migration 0024 settled on, for the same reason. `external_user_id` is carried beside it
because the two ids belong to different resources over there and enrolment needs the second.

**Nullable on purpose, both of them.** Provisioning a seat is four calls to two services and
none of it is transactional; the row is written as soon as the first one answers, so a
crash leaves a seat we can finish rather than an orphan we cannot find. `enrolled_at` and
`ai_enrolled_at` are therefore progress, not decoration: null means that half has not
happened yet and can be retried.

Revision ID: 0033
Revises: 0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_seats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # FK-free across modules (DATA_MODEL §8): the assessor lives in Identity. Unique
        # because a seat is per person — two would race for the same external identity.
        sa.Column("assessor_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_subject", sa.Text(), nullable=False),
        sa.Column("external_user_id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("enrolled_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("ai_enrolled_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("status in ('active','revoked')", name="ck_course_seats_status"),
        # Composite, so two providers can name the same subject without colliding — the
        # lesson of 0024, applied before there is a second provider to learn it from.
        sa.UniqueConstraint("provider", "external_subject", name="uq_course_seats_credential"),
    )


def downgrade() -> None:
    op.drop_table("course_seats")
