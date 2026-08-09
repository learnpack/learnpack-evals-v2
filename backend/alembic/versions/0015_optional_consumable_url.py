"""A consumable URL is an optional declaration of deployment (ADR-0028).

The column was NOT NULL because a human evaluator has to be able to open the course. That is
still why the field exists — but whether a deployed instance exists is a fact about the world
outside this system, and a package that has only been dropped into `courses/` has no answer to
give. ADR-0027 §5 hid that by minting the URL from the dev mount; the result 404s, because
serving a package's bytes is not deploying a course.

The backfill nulls exactly the rows carrying such a minted URL — a loopback host with
`/packages/` in the path. Everything else is a real declaration and is preserved: the seeder's
learn-pack.com courses and anything registered from a genuine http source. Nulling by structure
instead (the row's locators sitting under its consumable_url) was rejected: that is also the
shape of a legitimately http-registered package, whose locators are minted under the same base.

The backfill is the only repair. Re-registering an unchanged package is a reported no-op
(ADR-0027 §4) and never rewrites `contents`, so a minted URL not corrected here survives forever.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Host-anchored on purpose: a deployed host may legitimately serve a `/packages/` path, and
# only a loopback address can be the dev mount. Cannot match NULL, so re-running is a no-op.
# The test reads this constant rather than restating the predicate (test_consumable_url_backfill).
LOCAL_MOUNT_BACKFILL = r"""
UPDATE contents
   SET consumable_url = NULL
 WHERE consumable_url ~ '^https?://(localhost|127\.0\.0\.1|\[::1\])(:[0-9]+)?/'
   AND consumable_url LIKE '%/packages/%'
"""


def upgrade() -> None:
    # Loosen first, correct second: the UPDATE cannot run against the old constraint.
    op.alter_column("contents", "consumable_url", existing_type=sa.Text(), nullable=True)
    op.execute(LOCAL_MOUNT_BACKFILL)


def downgrade() -> None:
    # Asymmetric, like 0008's: the schema goes back, the data cannot. A row with no declared
    # URL is a real registration (a local course, a generated population); the old invariant
    # has no honest value to give it. Inventing one would put a 404 in front of an evaluator —
    # the defect this migration removed — and deleting the rows would take their assignments
    # and evaluations with them. So: refuse, and say how many stand in the way.
    undeclared = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM contents WHERE consumable_url IS NULL"))
        .scalar_one()
    )
    if undeclared:
        raise RuntimeError(
            f"{undeclared} content version(s) declare no consumable URL (ADR-0028); the column "
            "cannot go back to NOT NULL without inventing or deleting data — declare a URL for "
            "them, or drop them deliberately, first"
        )
    op.alter_column("contents", "consumable_url", existing_type=sa.Text(), nullable=False)
