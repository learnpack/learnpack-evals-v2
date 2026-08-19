"""The calibration dump — its arithmetic, its tolerance, and the identity line it must not cross.

The dump answers no criterion, so there is nothing here about pass or fail. What these tests
pin is what the dump computes for itself (direction, distance, zone), what it survives (a
quote that will not ground, a stray lesson, a duplicate concept), what it still refuses (a
`mode` outside its vocabulary), and — the one that matters beyond this file — that none of it
is part of `drafts-hybrid`'s identity.
"""

import json
from uuid import uuid4

import pytest

from app.modules.evaluation.domain.model import ProfileData, ProfileEntryData
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    calibration,
    prompts,
    runtime,
)
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.platform.llm import LlmCompletion


class FakeLlmClient:
    """The ADR-0034 seam: canned answer texts, so the feedback-retry loop runs for real."""

    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self.calls: list[dict] = []

    def complete(
        self,
        *,
        model,
        messages,
        temperature,
        max_tokens,
        response_format=None,
        extra_body=None,
        task_id=None,
    ):
        self.calls.append({"messages": list(messages), "task_id": task_id, "model": model})
        assert self._answers, "fake transport has no answer left"
        return LlmCompletion(
            text=self._answers.pop(0), model=model, tokens_in=100, tokens_out=40, latency_ms=7
        )


@pytest.fixture
def fake_llm(monkeypatch):
    def install(*answers: str) -> FakeLlmClient:
        client = FakeLlmClient(list(answers))
        monkeypatch.setattr(runtime, "get_client", lambda: client)
        return client

    return install


# --- profile builders -------------------------------------------------------------------


def entry(datum: str, value) -> ProfileEntryData:
    return ProfileEntryData(
        data_requirement_id=datum,
        provenance="declared_structured",
        value=value,
        quote=f"canonical serialization of {datum}",
        locator={"artifact": "lesson_plan"},
    )


def profile(**values) -> ProfileData:
    return ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV2",
        entries={datum: entry(datum, value) for datum, value in values.items()},
    )


def lesson(lesson_id: str, position: int) -> dict:
    return {
        "lessonId": lesson_id,
        "slug": f"lesson-{lesson_id}",
        "position": position,
        "title": f"Lesson {lesson_id}",
    }


def body(lesson_id: str, text: str) -> dict:
    return {"lessonSlug": f"lesson-{lesson_id}", "lessonId": lesson_id, "body": text}


# Four lessons: 00.0 and 03.0 are the frame ones, 01.0 teaches "recursion" and 02.0 teaches
# "memoization". 02.0 works with recursion (backward) and 01.0 mentions memoization, which
# the course only teaches later — the touch nothing measured before.
BACKWARD_QUOTE = "We reuse the recursive descent from the previous lesson on a new grammar."
FORWARD_QUOTE = "Assume the memoized table is already available while we trace the calls."


def four_lesson_profile() -> ProfileData:
    return profile(
        lesson_inventory=[
            lesson("00.0", 0),
            lesson("01.0", 1),
            lesson("02.0", 2),
            lesson("03.0", 3),
        ],
        lesson_bodies=[
            body("00.0", "# Welcome\n\nThis course is about recursion and its costs.\n"),
            body("01.0", f"# Recursion\n\nA function calling itself. {FORWARD_QUOTE}\n"),
            body("02.0", f"# Memoization\n\nCaching results. {BACKWARD_QUOTE}\n"),
            body("03.0", "# Wrap up\n\nYou can now reason about recursive cost.\n"),
        ],
        lesson_concept_coverage=[
            {"lessonId": "00.0", "concepts": []},
            {"lessonId": "01.0", "concepts": ["recursion"]},
            {"lessonId": "02.0", "concepts": ["memoization"]},
            {"lessonId": "03.0", "concepts": []},
        ],
    )


def answer(*entries: dict) -> str:
    return json.dumps({"lessons": list(entries)})


def touched(lesson_id: str, *touches: dict) -> dict:
    return {"lessonId": lesson_id, "touches": list(touches)}


def touch(
    index: int, quote: str, mode: str = "uses_as_known", newness: str = "new_context"
) -> dict:
    return {
        "conceptIndex": index,
        "reason": "because",
        "mode": mode,
        "newness": newness,
        "quote": quote,
    }


# --- what the code computes, never the model ---------------------------------------------


def test_direction_and_distance_come_from_the_plan(fake_llm):
    fake_llm(
        answer(
            touched("00.0"),
            touched("01.0", touch(1, FORWARD_QUOTE, mode="points_at", newness="n_a")),
            touched("02.0", touch(0, BACKWARD_QUOTE)),
            touched("03.0"),
        )
    )
    rows, summary, _ = calibration.dump_concept_touches(four_lesson_profile())

    by_lesson = {row.lesson_id: row for row in rows}
    assert by_lesson["02.0"].direction == "earlier"
    assert by_lesson["02.0"].distance == 1
    assert by_lesson["02.0"].taught_in == "01.0"
    # The forward touch is the one no criterion has ever been shown; it must survive intact.
    assert by_lesson["01.0"].direction == "later"
    assert by_lesson["01.0"].distance == 1
    assert summary.rows == 2
    assert summary.dropped == ()


def test_frame_lessons_are_shown_and_marked(fake_llm):
    client = fake_llm(answer(touched("00.0"), touched("01.0"), touched("02.0"), touched("03.0")))
    rows, summary, _ = calibration.dump_concept_touches(four_lesson_profile())

    assert summary.lessons == 4
    assert summary.frame_lessons == 2
    # Both frame bodies reach the prompt: a `newness` answer compares against the lesson that
    # teaches the concept, and hiding it is what made the earlier attempt unanswerable.
    corpus = "\n".join(message["content"] for message in client.calls[0]["messages"])
    assert "===== LESSON 00.0" in corpus
    assert "===== LESSON 03.0" in corpus
    assert rows == []


@pytest.mark.parametrize(
    ("offset", "length", "expected"),
    [
        (0, 5000, "opening"),
        (calibration.ZONE_WINDOW_CHARS - 1, 5000, "opening"),
        (calibration.ZONE_WINDOW_CHARS, 5000, "middle"),
        (3799, 5000, "middle"),
        (3800, 5000, "closing"),
        # A lesson shorter than one window is all opening: a head window shows all of it.
        (0, 900, "opening"),
        (899, 900, "opening"),
    ],
)
def test_zone_is_measured_against_the_bridge_window(offset, length, expected):
    assert calibration.zone_of(offset, length) == expected


def test_the_prompt_names_the_concepts_a_lesson_may_not_report(fake_llm):
    client = fake_llm(answer(touched("00.0"), touched("01.0"), touched("02.0"), touched("03.0")))
    calibration.dump_concept_touches(four_lesson_profile())

    corpus = "\n".join(message["content"] for message in client.calls[0]["messages"])
    assert "[0] taught in lesson 01.0: recursion" in corpus
    assert "(this lesson teaches concept 0 — do not report those)" in corpus
    assert "(this lesson teaches concept none — do not report those)" in corpus


# --- what a dump survives ----------------------------------------------------------------


def test_an_ungrounded_quote_loses_its_row_and_nothing_else(fake_llm):
    fake_llm(
        answer(
            touched("00.0"),
            touched("01.0"),
            touched("02.0", touch(0, BACKWARD_QUOTE), touch(0, "a sentence nobody wrote")),
            touched("03.0"),
        )
    )
    rows, summary, _ = calibration.dump_concept_touches(four_lesson_profile())

    # The duplicate index is dropped before the quote is even looked at; one good row stands.
    assert [row.quote for row in rows] == [BACKWARD_QUOTE]
    assert any("concept 0" in note for note in summary.dropped)


def test_a_quote_from_the_wrong_lesson_is_dropped_not_refused(fake_llm):
    fake_llm(
        answer(
            touched("00.0"),
            touched("01.0"),
            # The quote is real, but it belongs to 01.0 — grounding is per lesson.
            touched("02.0", touch(0, FORWARD_QUOTE)),
            touched("03.0"),
        )
    )
    rows, summary, _ = calibration.dump_concept_touches(four_lesson_profile())

    assert rows == []
    assert any("is not in that lesson" in note for note in summary.dropped)


def test_a_missing_lesson_and_a_stray_one_are_reported(fake_llm):
    fake_llm(
        answer(
            touched("00.0"),
            touched("99.9", touch(0, BACKWARD_QUOTE)),
            touched("02.0", touch(0, BACKWARD_QUOTE)),
            touched("03.0"),
        )
    )
    rows, summary, _ = calibration.dump_concept_touches(four_lesson_profile())

    assert len(rows) == 1
    assert any("'99.9'" in note for note in summary.dropped)
    assert any("no entry at all for lesson(s): 01.0" in note for note in summary.dropped)


def test_nothing_is_asked_when_the_course_declares_no_concept(fake_llm):
    fake_llm()  # no answer queued: reaching the transport would fail the test
    empty = profile(
        lesson_inventory=[lesson("00.0", 0)],
        lesson_bodies=[body("00.0", "# Welcome\n")],
        lesson_concept_coverage=[{"lessonId": "00.0", "concepts": []}],
    )
    rows, summary, usage = calibration.dump_concept_touches(empty)

    assert rows == []
    assert usage.calls == 0
    assert summary.dropped


# --- what a dump still refuses ------------------------------------------------------------


def test_a_mode_outside_the_vocabulary_is_a_contract_violation(fake_llm):
    bad = answer(touched("02.0", touch(0, BACKWARD_QUOTE, mode="applied")))
    good = answer(
        touched("00.0"),
        touched("01.0"),
        touched("02.0", touch(0, BACKWARD_QUOTE)),
        touched("03.0"),
    )
    client = fake_llm(bad, good)
    rows, _, usage = calibration.dump_concept_touches(four_lesson_profile())

    # Fed back and answered again: two calls, one row, and the feedback names the vocabulary.
    assert usage.calls == 2
    assert len(rows) == 1
    feedback = client.calls[1]["messages"][-1]["content"]
    assert "mode must be one of" in feedback


def test_a_persistent_violation_ends_the_dump(fake_llm):
    """Three distinct answers, all outside the vocabulary: the conversation runs out of
    attempts and raises, rather than yielding a table nobody can read."""
    fake_llm(
        *(
            answer(touched("02.0", touch(0, BACKWARD_QUOTE, newness=guess)))
            for guess in ("brand_new", "quite_new", "sort_of_new")
        )
    )
    with pytest.raises(AssessorExecutionError):
        calibration.dump_concept_touches(four_lesson_profile())


def test_the_validator_accepts_a_lesson_that_touches_nothing():
    assert calibration.validate_touches({"lessons": [{"lessonId": "01.0", "touches": []}]}, 3) == []


# --- what a reader gets --------------------------------------------------------------------


def test_the_table_carries_an_empty_column_for_the_readers_own_call(fake_llm):
    fake_llm(
        answer(
            touched("00.0"),
            touched("01.0"),
            touched("02.0", touch(0, BACKWARD_QUOTE)),
            touched("03.0"),
        )
    )
    rows, summary, usage = calibration.dump_concept_touches(four_lesson_profile())
    table = calibration.render_markdown(rows, summary, "recursion draft", usage)

    assert "| your call |" in table
    assert "no verdict" in table.lower()
    # One header, one separator, one row.
    assert len([line for line in table.splitlines() if line.startswith("| ")]) == 2
    assert BACKWARD_QUOTE in table
    # The same rows are readable again without a second call.
    assert (
        json.loads(calibration.as_json(rows, summary, usage))["rows"][0]["direction"] == "earlier"
    )


def test_a_quote_holding_a_pipe_does_not_break_its_row(fake_llm):
    piped = "The grammar is expr | term, which we already parsed."
    marked = profile(
        lesson_inventory=[lesson("01.0", 0), lesson("02.0", 1)],
        lesson_bodies=[
            body("01.0", "# Recursion\n\nA function calling itself.\n"),
            body("02.0", f"# More\n\n{piped}\n"),
        ],
        lesson_concept_coverage=[
            {"lessonId": "01.0", "concepts": ["recursion"]},
            {"lessonId": "02.0", "concepts": []},
        ],
    )
    fake_llm(answer(touched("01.0"), touched("02.0", touch(0, piped))))
    rows, summary, usage = calibration.dump_concept_touches(marked)
    table = calibration.render_markdown(rows, summary, "piped", usage)

    row_line = next(line for line in table.splitlines() if "expr" in line)
    assert "expr \\| term" in row_line
    # The escaped pipe is inside a cell, so the row still has exactly its own delimiters.
    assert row_line.replace("\\|", "").count("|") == len(calibration._COLUMNS) + 1


# --- the line this module must not cross ---------------------------------------------------


def test_the_calibration_prompts_are_not_part_of_the_assessor_identity():
    """A prompt in `_ALL_TEMPLATES` moves the fingerprint, and a moved fingerprint is a new
    version of `drafts-hybrid` that every ratification has to be redone against. This dump
    decides nothing, so it must cost nobody a ratification."""
    templates = set(prompts._ALL_TEMPLATES.values())
    assert calibration.CONCEPT_TOUCHES_SYSTEM not in templates
    assert calibration.CONCEPT_TOUCHES_USER.template not in templates


def test_no_executor_reads_the_dump():
    """The other half of the same rule: if an executor ever imported this, the dump would be
    deciding outcomes and everything above would be false."""
    from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import executors

    assert not hasattr(executors, "calibration")
