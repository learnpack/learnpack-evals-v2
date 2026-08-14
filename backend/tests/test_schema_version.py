"""The guard that would have caught the incident: a schema behind the code, named at a door.

What is pinned here is the message as much as the refusal. The three states a mismatch can
be in want three different remedies, and naming the wrong one is what makes such a message
harmful rather than merely useless — a database AHEAD of the checkout is not fixed by
migrating.
"""

import logging

import pytest

from app.platform import schema_version
from app.platform.schema_version import drift

KNOWN = frozenset({"0001", "0017", "0018"})


# ------------------------------------------------------------------ what the complaint says


def test_a_database_at_head_has_nothing_to_say():
    assert drift("0018", "0018", KNOWN) is None


def test_a_database_that_was_never_migrated_is_told_to_migrate():
    complaint = drift(None, "0018", KNOWN)
    assert complaint is not None
    assert "never been migrated" in complaint
    assert "alembic upgrade head" in complaint


def test_a_database_behind_the_code_names_both_revisions_and_the_command():
    """The incident, exactly: 0017 under code that expects 0018."""
    complaint = drift("0017", "0018", KNOWN)
    assert complaint is not None
    assert "0017" in complaint and "0018" in complaint
    assert "alembic upgrade head" in complaint
    # Why it matters that this is said at the door: the alternative is finding out from a
    # statement that fails partway through the work.
    assert "halfway" in complaint


def test_a_database_ahead_of_the_checkout_is_not_told_to_migrate():
    """The stale thing is the code, and migrating would not fix it — telling someone to run
    a migration here sends them to do something that cannot work."""
    complaint = drift("0019", "0018", KNOWN)
    assert complaint is not None
    assert "does not know" in complaint
    assert "alembic upgrade head" not in complaint
    assert "pulling" in complaint


# ------------------------------------------------------------------ what a door does with it


def test_a_local_door_refuses_to_start_and_the_message_is_what_is_read(monkeypatch):
    monkeypatch.setattr(schema_version, "current_revision", lambda: "0017")
    monkeypatch.setattr(schema_version, "head_revision", lambda: "0018")
    monkeypatch.setattr(schema_version, "known_revisions", lambda: KNOWN)

    with pytest.raises(SystemExit) as refused:
        schema_version.verify(refuse=True)

    assert "REFUSING TO START" in str(refused.value)
    assert "alembic upgrade head" in str(refused.value)


def test_anywhere_else_it_warns_and_lets_the_process_live(monkeypatch, caplog):
    """A deploy may start the process while the migration step is still running: refusing
    there would break the thing this exists to protect."""
    monkeypatch.setattr(schema_version, "current_revision", lambda: "0017")
    monkeypatch.setattr(schema_version, "head_revision", lambda: "0018")
    monkeypatch.setattr(schema_version, "known_revisions", lambda: KNOWN)

    with caplog.at_level(logging.WARNING):
        schema_version.verify(refuse=False)  # does not raise

    assert any("0017" in record.getMessage() for record in caplog.records)


def test_a_database_at_head_says_nothing_at_all(monkeypatch, caplog):
    monkeypatch.setattr(schema_version, "current_revision", lambda: "0018")
    monkeypatch.setattr(schema_version, "head_revision", lambda: "0018")
    monkeypatch.setattr(schema_version, "known_revisions", lambda: KNOWN)

    with caplog.at_level(logging.WARNING):
        schema_version.verify(refuse=True)

    assert caplog.records == []


def test_an_unreachable_database_is_not_this_checks_news(monkeypatch, caplog):
    """It would be a lie in the one place someone is looking for the truth: a connection
    refused is a different failure, with its own reporting."""

    def unreachable():
        raise OSError("connection refused")

    monkeypatch.setattr(schema_version, "current_revision", unreachable)

    with caplog.at_level(logging.WARNING):
        schema_version.verify(refuse=True)  # does not raise, even where it would refuse

    assert caplog.records == []


# ------------------------------------------------------------------ against the real thing


def test_the_test_database_is_at_head(session):
    """A canary for the harness itself: the suite migrates before it runs (`conftest`), so
    if this ever fails it is because that stopped happening — which is precisely the blind
    spot that let a stale development database through."""
    assert schema_version.current_revision() == schema_version.head_revision()
    assert schema_version.head_revision() in schema_version.known_revisions()
