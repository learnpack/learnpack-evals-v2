"""A credential is `(provider, subject)`, not a column named after one vendor.

`assessors.clerk_user_id` put a vendor's name inside the pure domain, and it had already
stopped being true: ADR-0008 added a second adapter, and local mode stores `local|<email>`
in a column called `clerk_`. The prefix existed to keep the two namespaces from colliding in
one unique column — which is exactly what a composite key does properly, so the split drops
it as it goes.

No behaviour changes and no decision is revisited. The backfill states what each row already
was: anything prefixed `local|` came from the local adapter (ADR-0008), everything else from
Clerk (ADR-0004). There is no third source, and a row that matched neither could not exist —
`get_by_clerk_user_id` was the only lookup and both adapters wrote through it.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assessors", sa.Column("auth_provider", sa.Text()))
    op.add_column("assessors", sa.Column("auth_subject", sa.Text()))

    # A statement about the rows that exist, made once — not a default that would let a
    # future insert mean "clerk" by forgetting to say anything.
    op.execute(
        """
        UPDATE assessors
           SET auth_provider = CASE
                   WHEN clerk_user_id LIKE 'local|%' THEN 'local'
                   ELSE 'clerk'
               END,
               auth_subject = CASE
                   WHEN clerk_user_id LIKE 'local|%' THEN substring(clerk_user_id from 7)
                   ELSE clerk_user_id
               END
         WHERE clerk_user_id IS NOT NULL
        """
    )

    op.drop_constraint("ck_assessors_kind_shape", "assessors", type_="check")
    op.drop_column("assessors", "clerk_user_id")

    op.create_check_constraint(
        "ck_assessors_kind_shape",
        "assessors",
        "(kind = 'human' and auth_provider is not null and auth_subject is not null) or "
        "(kind = 'automated' and source_config is not null and auth_provider is null "
        "and auth_subject is null)",
    )
    # Composite, so two providers can name the same subject without colliding. That is what
    # the `local|` prefix was standing in for.
    op.create_unique_constraint(
        "uq_assessors_credential", "assessors", ["auth_provider", "auth_subject"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_assessors_credential", "assessors", type_="unique")
    op.drop_constraint("ck_assessors_kind_shape", "assessors", type_="check")
    op.add_column("assessors", sa.Column("clerk_user_id", sa.Text()))
    op.execute(
        """
        UPDATE assessors
           SET clerk_user_id = CASE
                   WHEN auth_provider = 'local' THEN 'local|' || auth_subject
                   ELSE auth_subject
               END
         WHERE auth_subject IS NOT NULL
        """
    )
    op.create_unique_constraint("assessors_clerk_user_id_key", "assessors", ["clerk_user_id"])
    op.create_check_constraint(
        "ck_assessors_kind_shape",
        "assessors",
        "(kind = 'human' and clerk_user_id is not null) or "
        "(kind = 'automated' and source_config is not null and clerk_user_id is null)",
    )
    op.drop_column("assessors", "auth_subject")
    op.drop_column("assessors", "auth_provider")
