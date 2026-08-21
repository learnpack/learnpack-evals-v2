"""Registering a human evaluator is an invitation, not an account (ADR-0049).

`assessor_invitations` holds the act an admin takes: who was asked in, by whom, with which
role and expertise, and until when it can be used. The `assessors` row still appears at the
first login (ADR-0004) — nothing about that changed, and this table deliberately carries no
credential, which is what keeps ADR-0007's refusal ("seeding an admin row by email") intact.

**No `expired` value exists here.** Expiry is derived from `expires_at` every time it is
asked, so a row cannot sit claiming to be pending while the clock says otherwise, and no job
is needed to keep it honest.

**The partial unique index is the backstop, not the rule.** At most one pending invitation
per address — the use case raises a clean 409 first, the way `AssignContent` does over
`ix_assignments_active`. It is partial because accepting and revoking must leave the address
free to be invited again.

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessor_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="evaluator"),
        sa.Column("display_name", sa.Text()),
        # The expertise profile the GLOSSARY gives a human assessor. Typed at invitation
        # time because that is when somebody knows it; it lands on the assessor at redemption.
        sa.Column("expertise", sa.Text()),
        # FK-free across modules, like every other id a module holds (13-code §2) — but this
        # one points inside Identity itself, so it can be a real reference.
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessors.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "accepted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessors.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('pending','accepted','revoked')", name="ck_assessor_invitations_status"
        ),
        sa.CheckConstraint("role in ('admin','evaluator')", name="ck_assessor_invitations_role"),
        # An accepted invitation names what it produced, and only an accepted one does.
        sa.CheckConstraint(
            "(status = 'accepted' and accepted_by is not null) or "
            "(status <> 'accepted' and accepted_by is null)",
            name="ck_assessor_invitations_accepted_by",
        ),
    )
    op.create_index(
        "ix_assessor_invitations_pending_email",
        "assessor_invitations",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_assessor_invitations_status", "assessor_invitations", ["status", "expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_assessor_invitations_status", table_name="assessor_invitations")
    op.drop_index("ix_assessor_invitations_pending_email", table_name="assessor_invitations")
    op.drop_table("assessor_invitations")
