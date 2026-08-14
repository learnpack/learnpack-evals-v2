"""A study is named and described, and the act that closes it is a signature (ADR-0043).

Three renames and one deletion.

* `purpose` becomes `name`: the column always held a title, and the GLOSSARY reserves
  *purpose* for a typology (initial / regression / comparison) this does not build. A rename
  keeps every row — what was typed as a purpose reads correctly as a name.
* `description` is added, optional. Nothing backfills it: an absent description is absent.
* `published` becomes `signed_off`, in the status, in both columns and in the event stream.
  Nothing is published by that act — the report was readable before it (ADR-0041) — and what
  it adds is `published_by`, a signature, under a name that says so.

**This migration deletes every frozen report** (ADR-0043 §11), because what `compose_report`
writes changed and no report anyone relies on exists yet: the deploy has not happened. A
study that carried one returns to `open`, unsigned, and can be signed off again — its
judgments, evidence and dataset are untouched. `downgrade` restores the structure; it does
not restore the rows, and nothing could.

Revision ID: 0020
Revises: 0019
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("declared", "prepared", "open", "signed_off")
OLD_STATUSES = ("declared", "prepared", "open", "published")


def _status_check(values: tuple[str, ...]) -> str:
    return "status IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.alter_column("studies", "purpose", new_column_name="name")
    op.add_column("studies", sa.Column("description", sa.Text(), nullable=True))
    op.alter_column("studies", "published_at", new_column_name="signed_off_at")
    op.alter_column("studies", "published_by", new_column_name="signed_off_by")
    op.alter_column("study_reports", "published_at", new_column_name="signed_off_at")

    # The frozen documents go before the status that pointed at them, so no study is ever
    # left claiming a report that is not there.
    op.execute("DELETE FROM study_reports")
    op.execute(
        "UPDATE studies "
        "   SET status = 'open', signed_off_at = NULL, signed_off_by = NULL "
        " WHERE status = 'published'"
    )

    op.drop_constraint("ck_studies_status", "studies", type_="check")
    op.create_check_constraint("ck_studies_status", "studies", _status_check(STATUSES))


def downgrade() -> None:
    # Structure only. The reports `upgrade` deleted are gone, and a study that had been
    # signed off comes back as `open` — which is what it now is.
    op.drop_constraint("ck_studies_status", "studies", type_="check")
    op.create_check_constraint("ck_studies_status", "studies", _status_check(OLD_STATUSES))

    op.alter_column("study_reports", "signed_off_at", new_column_name="published_at")
    op.alter_column("studies", "signed_off_by", new_column_name="published_by")
    op.alter_column("studies", "signed_off_at", new_column_name="published_at")
    op.drop_column("studies", "description")
    op.alter_column("studies", "name", new_column_name="purpose")
