"""Refusing to work against a database the code has outgrown.

A batch died mid-course with `UndefinedColumn: column "execution_cause" does not exist`.
Nothing was wrong with the code: the development database was one migration behind, and the
test database never is — the suite migrates it at session start, so green tests say nothing
about the store you actually run against. The fact that would have caught it was available
before the first LLM call: `alembic_version` against this checkout's head.

Cheap to ask, so it is asked at the doors rather than discovered on the first statement that
needs the missing column — which is how it cost a half-spent evaluation instead of a second.

**Local refuses; anything else warns.** Refusing is the idiom ADR-0008 already set for a
local box: a configuration nobody can work honestly with does not boot (`AUTH_MODE=local`
with `ENVIRONMENT=production` does not either). Off a dev box it can only warn, because a
deploy may legitimately start a process while the migration step is still running, and
refusing there would break the deploy this exists to protect.

**A database it cannot reach says nothing.** That is a different failure with its own
reporting — `/health`, or the first command's own error — and answering "your schema is
stale" to a connection refused would be a lie in the one place someone is looking for the
truth.
"""

import logging
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.platform.db import get_engine

logger = logging.getLogger(__name__)

# `backend/`, where `alembic.ini` and `alembic/` live — the same relative walk `cli.REPO_ROOT`
# does one level up.
BACKEND_ROOT = Path(__file__).resolve().parents[2]

UPGRADE = "uv run alembic upgrade head  (from backend/)"


@lru_cache
def _scripts() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def head_revision() -> str:
    """The revision this checkout expects the database to be at."""
    head = _scripts().get_current_head()
    if head is None:  # pragma: no cover — a repo with no migrations at all
        raise RuntimeError("this checkout declares no migrations")
    return head


def known_revisions() -> frozenset[str]:
    return frozenset(script.revision for script in _scripts().walk_revisions())


def current_revision() -> str | None:
    """What the database says it is at, or `None` if it was never migrated."""
    with get_engine().connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def drift(current: str | None, head: str, known: frozenset[str]) -> str | None:
    """The complaint, or `None` when the two agree.

    Three states, three different remedies — and naming the wrong one is what makes a
    message harmful rather than merely useless. A database ahead of the checkout is NOT
    fixed by migrating: the stale thing is the code.
    """
    if current == head:
        return None
    if current is None:
        return (
            f"this database has never been migrated, and the code expects revision {head}. "
            f"Run: {UPGRADE}"
        )
    if current in known:
        return (
            f"this database is at revision {current} and the code expects {head}: it is "
            f"behind, and a statement that needs a newer column will fail halfway through "
            f"whatever is running. Run: {UPGRADE}"
        )
    return (
        f"this database is at revision {current}, which this checkout does not know — it was "
        f"migrated by newer code, and the stale one here is the checkout (expected {head}). "
        "Migrating would not fix it; pulling would."
    )


def verify(*, refuse: bool) -> None:
    """Check the schema at a door. Refuse to continue, or warn, per the caller's mode."""
    try:
        current = current_revision()
    except Exception as exc:  # noqa: BLE001 — an unreachable database is not this check's news
        logger.debug("could not read the schema revision (%s); skipping the check", exc)
        return

    complaint = drift(current, head_revision(), known_revisions())
    if complaint is None:
        return
    if refuse:
        # The message is what has to be read, not a stack: `SystemExit` prints it and stops.
        raise SystemExit(f"REFUSING TO START: {complaint}")
    logger.warning("the database schema is not what this code expects: %s", complaint)
