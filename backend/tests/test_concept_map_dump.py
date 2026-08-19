"""The concept-major dump: what it hides from the model, and what it joins afterwards.

This shape exists because the lesson-major one is unstable where its SHAPE makes it so, and
because the plan's concept-to-lesson assignment was entangled with the answer. So the two
things worth pinning here are that the assignment never reaches the prompt, and that it is
joined back onto every row — a `defined_in` row the plan does not declare is the finding the
whole shape was built to surface.
"""

import json
from uuid import uuid4

import pytest

from app.modules.evaluation.domain.model import ProfileData, ProfileEntryData
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import calibration, runtime
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.platform.llm import LlmCompletion


class FakeLlmClient:
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
        self.calls.append({"messages": list(messages), "task_id": task_id})
        assert self._answers, "fake transport has no answer left"
        return LlmCompletion(
            text=self._answers.pop(0), model=model, tokens_in=90, tokens_out=30, latency_ms=5
        )


@pytest.fixture
def fake_llm(monkeypatch):
    def install(*answers: str) -> FakeLlmClient:
        client = FakeLlmClient(list(answers))
        monkeypatch.setattr(runtime, "get_client", lambda: client)
        return client

    return install


def entry(datum: str, value) -> ProfileEntryData:
    return ProfileEntryData(
        data_requirement_id=datum, provenance="declared_structured", value=value, quote=datum
    )


def lesson(lesson_id: str, position: int) -> dict:
    return {"lessonId": lesson_id, "position": position, "title": f"Lesson {lesson_id}"}


def body(lesson_id: str, text: str) -> dict:
    return {"lessonSlug": f"l-{lesson_id}", "lessonId": lesson_id, "body": text}


DEFINES = "A closure is a function that keeps the bindings of the scope it was made in."
USES = "We wrap the counter in a closure so each button keeps its own tally."


# The plan declares "closure" for 02.0, but the prose defines it in 01.0 — the exact shape of
# the defect two annotators found unprompted, and the one this dump exists to measure.
def a_profile() -> ProfileData:
    values = {
        "lesson_inventory": [lesson("00.0", 0), lesson("01.0", 1), lesson("02.0", 2)],
        "lesson_bodies": [
            body("00.0", "# Welcome\n\nThis course is about functions.\n"),
            body("01.0", f"# Scope\n\n{DEFINES}\n"),
            body("02.0", f"# Counters\n\n{USES}\n"),
        ],
        "lesson_concept_coverage": [
            {"lessonId": "00.0", "concepts": []},
            {"lessonId": "01.0", "concepts": ["scope"]},
            # Declared twice under one name, in two lessons — the merge case.
            {"lessonId": "02.0", "concepts": ["closure", "Closure"]},
        ],
    }
    return ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV2",
        entries={datum: entry(datum, value) for datum, value in values.items()},
    )


def concept(index: int, **buckets) -> dict:
    out = {"conceptIndex": index}
    for name in calibration.BUCKETS:
        out[name] = [{"lessonId": lid, "quote": quote} for lid, quote in buckets.get(name, [])]
    return out


def answer(*entries: dict) -> str:
    return json.dumps({"concepts": list(entries)})


# --- what the model is and is not told ---------------------------------------------------


def test_the_prompt_never_says_where_a_concept_is_taught(fake_llm):
    client = fake_llm(answer(concept(0), concept(1)))
    calibration.dump_concept_map(a_profile())

    prompt = "\n".join(message["content"] for message in client.calls[0]["messages"])
    assert "[0] scope" in prompt
    assert "[1] closure" in prompt
    # The lesson-major dump labels every concept with its lesson and tells each block which
    # numbers are its own. Both would hand the model the answer this shape is measuring.
    assert "taught in lesson" not in prompt
    assert "do not report those" not in prompt


def test_a_name_declared_twice_becomes_one_concept():
    concepts = calibration.distinct_concepts(a_profile())
    assert [c["concept"] for c in concepts] == ["scope", "closure"]
    # Both spellings collapse, and the lesson each was declared in survives on the entry.
    assert concepts[1]["declaredIn"] == ("02.0",)


# --- what is joined back on ----------------------------------------------------------------


def test_the_plan_is_joined_after_the_answer_and_can_disagree_with_it(fake_llm):
    fake_llm(
        answer(
            concept(0),
            concept(1, defined_in=[("01.0", DEFINES)], used_as_known_in=[("02.0", USES)]),
        )
    )
    rows, summary, _ = calibration.dump_concept_map(a_profile())

    defined = next(r for r in rows if r.bucket == "defined_in")
    assert defined.lesson_id == "01.0"
    assert defined.declared_in == ("02.0",)
    # The finding: the prose defines it where the plan does not declare it.
    assert defined.declared_here is False
    used = next(r for r in rows if r.bucket == "used_as_known_in")
    assert used.declared_here is True
    assert summary.found == 1


def test_every_group_reaches_a_row_with_its_own_zone(fake_llm):
    fake_llm(answer(concept(0), concept(1, mentioned_in=[("02.0", USES)])))
    rows, _, _ = calibration.dump_concept_map(a_profile())

    assert [r.bucket for r in rows] == ["mentioned_in"]
    assert rows[0].zone == "opening"


# --- what a dump survives, and what it still refuses ---------------------------------------


def test_a_quote_that_will_not_ground_costs_its_row(fake_llm):
    fake_llm(
        answer(
            concept(0),
            concept(1, defined_in=[("01.0", "a sentence nobody wrote")]),
        )
    )
    rows, summary, usage = calibration.dump_concept_map(a_profile())

    assert rows == []
    assert usage.calls == 1
    assert any("quote not in that lesson" in note for note in summary.dropped)


def test_a_concept_nobody_answered_for_is_reported(fake_llm):
    fake_llm(answer(concept(1, defined_in=[("01.0", DEFINES)])))
    _, summary, _ = calibration.dump_concept_map(a_profile())

    assert any("no entry at all for concept(s): [0]" in note for note in summary.dropped)


def test_a_group_outside_the_five_is_a_contract_violation(fake_llm):
    bad = json.dumps({"concepts": [{"conceptIndex": 0, "taught_in": []}]})
    good = answer(concept(0), concept(1))
    client = fake_llm(bad, good)
    rows, _, usage = calibration.dump_concept_map(a_profile())

    assert usage.calls == 2
    assert rows == []
    assert "not one of the five groups" in client.calls[1]["messages"][-1]["content"]


def test_a_persistent_violation_ends_the_dump(fake_llm):
    fake_llm(
        *(json.dumps({"concepts": [{"conceptIndex": 0, name: []}]}) for name in ("a", "b", "c"))
    )
    with pytest.raises(AssessorExecutionError):
        calibration.dump_concept_map(a_profile())


def test_more_lessons_than_the_cap_is_refused():
    over = {"conceptIndex": 0, "defined_in": [{"lessonId": "x", "quote": "q"}] * 7}
    assert calibration.validate_concept_map({"concepts": [over]}, 2)


# --- what a reader gets ---------------------------------------------------------------------


def test_the_table_shows_the_plan_beside_the_answer(fake_llm):
    fake_llm(answer(concept(0), concept(1, defined_in=[("01.0", DEFINES)])))
    rows, summary, usage = calibration.dump_concept_map(a_profile())
    table = calibration.render_map_markdown(rows, summary, "closures draft", usage)

    assert "| your call |" in table
    assert "| plan declares it in |" in table
    assert "02.0" in table  # what the plan says, beside the lesson the model answered
    assert json.loads(calibration.map_as_json(rows, summary, usage))["rows"][0]["bucket"] == (
        "defined_in"
    )


def test_the_map_prompts_are_not_part_of_the_assessor_identity():
    from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import prompts

    templates = set(prompts._ALL_TEMPLATES.values())
    assert calibration.CONCEPT_MAP_SYSTEM not in templates
    assert calibration.CONCEPT_MAP_USER.template not in templates
