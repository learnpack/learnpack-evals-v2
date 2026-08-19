"""`dump-concept-touches`: what it writes, and the three things it refuses to guess.

The dump itself is pinned by `test_concept_touch_dump.py`; what is pinned here is the
command around it — that it reads the profile through the same gateway `evaluate` reads,
that it names a missing precondition instead of raising through it, and that a run leaves
two files a person can open.
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest

import app.cli as cli
from app.modules.evaluation.domain.model import ProfileData, ProfileEntryData
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import calibration


def entry(datum: str, value) -> ProfileEntryData:
    return ProfileEntryData(
        data_requirement_id=datum, provenance="declared_structured", value=value, quote=datum
    )


def profile_with(**values) -> ProfileData:
    return ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV2",
        entries={datum: entry(datum, value) for datum, value in values.items()},
    )


@pytest.fixture
def answered(monkeypatch):
    """The profile the gateway returns, and a dump that never reaches the transport."""

    def install(profile: ProfileData | None, rows=(), dropped=()) -> None:
        monkeypatch.setattr(cli.ProfilingGateway, "get_profile", lambda self, content_id: profile)
        summary = calibration.DumpSummary(
            lessons=4, frame_lessons=2, concepts=2, rows=len(rows), dropped=tuple(dropped)
        )
        usage = calibration.LlmUsage(
            model=calibration.MODEL, calls=1, tokens_in=900, tokens_out=120, latency_ms=30
        )
        monkeypatch.setattr(
            calibration, "dump_concept_touches", lambda p: (list(rows), summary, usage)
        )

    return install


def a_row(**overrides) -> calibration.ConceptTouchRow:
    fields = {
        "lesson_id": "02.0",
        "lesson_position": 2,
        "is_frame": False,
        "concept_index": 0,
        "concept": "recursion",
        "taught_in": "01.0",
        "taught_position": 1,
        "direction": "earlier",
        "distance": 1,
        "mode": "uses_as_known",
        "newness": "new_context",
        "zone": "opening",
        "offset": 40,
        "quote": "We reuse the recursive descent on a new grammar.",
    }
    return calibration.ConceptTouchRow(**{**fields, **overrides})


def test_a_content_id_that_is_not_one_is_refused_before_anything_opens(capsys):
    assert cli.run_dump_concept_touches("not-a-uuid", Path("unused")) == 1
    assert "invalid content id" in capsys.readouterr().err


def test_a_content_with_no_ok_profile_is_named_not_raised_through(
    requires_db, answered, capsys, tmp_path
):
    answered(None)
    assert cli.run_dump_concept_touches(str(uuid4()), tmp_path) == 1
    assert "no ok profile" in capsys.readouterr().err


def test_a_profile_without_the_concept_map_says_so(requires_db, answered, capsys, tmp_path):
    """A format whose adapter supplies no concept coverage cannot be dumped, and that is a
    fact about the adapter rather than a failure here."""
    answered(profile_with(lesson_bodies=[], lesson_inventory=[]))
    assert cli.run_dump_concept_touches(str(uuid4()), tmp_path) == 1
    assert "lesson_concept_coverage" in capsys.readouterr().err


def test_an_absent_entry_counts_as_missing(requires_db, answered, capsys, tmp_path, monkeypatch):
    absent = ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV2",
        entries={
            "lesson_bodies": entry("lesson_bodies", []),
            "lesson_inventory": entry("lesson_inventory", []),
            "lesson_concept_coverage": ProfileEntryData(
                data_requirement_id="lesson_concept_coverage", provenance="absent"
            ),
        },
    )
    answered(absent)
    assert cli.run_dump_concept_touches(str(uuid4()), tmp_path) == 1
    assert "lesson_concept_coverage" in capsys.readouterr().err


def test_a_run_leaves_a_table_and_its_rows(requires_db, answered, capsys, tmp_path):
    content_id = uuid4()
    answered(
        profile_with(lesson_bodies=[], lesson_inventory=[], lesson_concept_coverage=[]),
        rows=[a_row(), a_row(lesson_id="03.0", direction="later", distance=2)],
        dropped=["lesson 01.0: a touch on concept 9"],
    )
    assert cli.run_dump_concept_touches(str(content_id), tmp_path) == 0

    table = tmp_path / f"concept-touches-{content_id}.md"
    data = tmp_path / f"concept-touches-{content_id}.json"
    assert "| your call |" in table.read_text(encoding="utf-8")
    assert len(json.loads(data.read_text(encoding="utf-8"))["rows"]) == 2

    out = capsys.readouterr()
    # The direction counts are the first thing a reader needs: `later` is the touch nothing
    # has ever been shown, so a run that found none should say so on the terminal.
    assert "earlier=1, later=1" in out.out
    assert "not yielded" in out.err
