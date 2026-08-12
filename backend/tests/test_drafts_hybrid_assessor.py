"""`drafts-hybrid` v5 — the semantic and judged executors over a fake transport, the
coverage vs the real v5 YAML, the whole package against the frozen LearnpackV2 fixture,
and ratification.

The fake replaces the TRANSPORT only (the seam is `runtime.get_client`, ADR-0034):
everything semantic — prompts, validation, grounding, feedback retries, the decision
constants — runs for real. The structural seven are copies whose arithmetic is already
pinned by the structural test files; here they appear through the whole-package run.

For the judged criteria the suite cannot pin whether a verdict is RIGHT — that is what
calibration against the real model and a human reading it are for. What it pins is
everything around the verdict, which is where this design can break silently: that the
question carries the instrument's own words, that the quote is checked against the text
shown, that a failure mode outside the criterion's declared list is refused, and that two
criteria reading one answer pay for it once.

What the decision constants do is pinned here on synthetic sequences (the calibration of
the RULES); what the real model answers is the manual `evaluate --dry-run` loop's
business, never the suite's — no test touches the network.
"""

import copy
import dataclasses
import json
from uuid import uuid4

import pytest
import yaml
from test_automated_evaluation_flow import publish_instrument, track_automated
from test_learnpack_v2_extraction import extract_fixture

from app.cli import run_ratify_assessor
from app.modules.evaluation.domain.derivation import derive_and_execute
from app.modules.evaluation.domain.model import (
    BindingSpec,
    ClaimSpec,
    CriterionSpec,
    InstrumentSpec,
    ProfileData,
    ProfileEntryData,
)
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS, drafts_hybrid
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    judgments,
    runtime,
    tasks,
)
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from app.platform.llm import LlmCompletion, LlmTransportError
from tests.conftest import INSTRUMENTS_DIR

PACKAGE = AUTOMATED_ASSESSORS[("drafts-hybrid", "5")]

_V5_SPEC = yaml.safe_load(
    (INSTRUMENTS_DIR / "course-drafts-qa-v5.yaml").read_text(encoding="utf-8")
)
_V5_CRITERIA = {
    raw["id"]: CriterionSpec(
        criterion_id=raw["id"],
        pass_condition=raw["pass_condition"],
        failure_modes=tuple(raw["failure_modes"]),
        claim_ids=tuple(raw["claims"]),
        required_data=tuple(raw["requires"]),
        on_missing_evidence=raw.get("on_missing_evidence", "no_evidence"),
        condition=raw.get("condition"),
    )
    for raw in _V5_SPEC["criteria"]
}


# --- the fake transport (the ADR-0034 seam) --------------------------------------------


class FakeLlmClient:
    """Routes each call to a canned-answer queue: by `task_id` when the test named one,
    otherwise by the task tag in the user prompt (how the v2 extraction tasks are fed).

    Queues hold raw response TEXTS so a test can feed one bad answer and then a good one —
    the feedback-retry loop runs for real against them."""

    def __init__(
        self,
        outcomes: list[str] | None = None,
        objectives: list[str] | None = None,
        trajectory: list[str] | None = None,
        **by_task: list[str],
    ) -> None:
        self._queues = {
            "<lesson>": list(outcomes or []),
            "<objectives>": list(objectives or []),
            "<plan>": list(trajectory or []),
        }
        self._by_task = {task_id: list(answers) for task_id, answers in by_task.items()}
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
        self.calls.append(
            {
                "model": model,
                "messages": list(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
                "extra_body": extra_body,
                "task_id": task_id,
            }
        )
        if task_id in self._by_task:
            queue = self._by_task[task_id]
            assert queue, f"fake transport has no answer left for task {task_id!r}"
            return LlmCompletion(
                text=queue.pop(0), model=model, tokens_in=100, tokens_out=40, latency_ms=7
            )
        prompt_text = "\n".join(m["content"] for m in messages)
        for tag, queue in self._queues.items():
            if tag in prompt_text:
                assert queue, f"fake transport has no answer left for {tag}"
                return LlmCompletion(
                    text=queue.pop(0), model=model, tokens_in=100, tokens_out=40, latency_ms=7
                )
        raise AssertionError(f"no queue for task {task_id!r} and no task tag in the prompt")


@pytest.fixture(autouse=True)
def isolated_task_cache():
    drafts_hybrid.clear_caches()
    yield
    drafts_hybrid.clear_caches()


@pytest.fixture
def fake_llm(monkeypatch):
    def install(**queues) -> FakeLlmClient:
        client = FakeLlmClient(**queues)
        monkeypatch.setattr(runtime, "get_client", lambda: client)
        return client

    return install


# --- profile builders (the drafts test file's helpers, plus lessonId on bodies) --------


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
        "type": "lesson",
        "title": f"Lesson {lesson_id}",
    }


def body(lesson_id: str, text: str) -> dict:
    return {"lessonSlug": f"lesson-{lesson_id}", "lessonId": lesson_id, "body": text}


OPENING_BODY = (
    "# Welcome\n\nBy the end of this course you will be able to build a complete web "
    "page from scratch. We will move step by step.\n"
)
GROUNDED_OUTCOME = "By the end of this course you will be able to build a complete web page"


def outcomes_json(*items: tuple[str, str, bool]) -> str:
    return json.dumps(
        {
            "outcomes": [
                {"statement": statement, "verb": verb, "is_observable": observable}
                for statement, verb, observable in items
            ]
        }
    )


def objectives_json(*levels: tuple[str, bool]) -> str:
    return json.dumps(
        {
            "objectives": [
                {"index": index, "verb": "verb", "is_observable": observable, "bloom_level": level}
                for index, (level, observable) in enumerate(levels)
            ]
        }
    )


def trajectory_json(levels: dict[str, int]) -> str:
    return json.dumps(
        {
            "lessons": [
                {"lessonId": lesson_id, "level": level} for lesson_id, level in levels.items()
            ]
        }
    )


def outcomes_profile() -> ProfileData:
    return profile(
        lesson_inventory=[lesson("00.0", 0), lesson("01.0", 1), lesson("01.1", 2)],
        lesson_bodies=[
            body("00.0", OPENING_BODY),
            body("01.0", "# Topic\n\nContent."),
            body("01.1", "# Topic 2\n\nMore content."),
        ],
    )


# --- coverage vs the shipped instrument ------------------------------------------------


def test_coverage_is_a_disjoint_union_over_v5():
    declared = {raw["id"] for raw in _V5_SPEC["criteria"]}
    assert PACKAGE.coverage.declared == declared
    assert not (PACKAGE.coverage.executes & set(PACKAGE.coverage.abstains))
    assert PACKAGE.instrument_id == _V5_SPEC["instrument_id"]
    assert len(PACKAGE.coverage.executes) == 19


def test_coverage_also_decides_every_criterion_of_the_older_versions():
    """Criterion ids are stable across the lineage (v3 changed one criterion's `requires`,
    v4 two pass conditions and v5 a third, none of them touching an id), so the one
    artifact can ratify any published version (ADR-0019)."""
    for version in ("v1", "v2", "v3", "v4"):
        spec = yaml.safe_load(
            (INSTRUMENTS_DIR / f"course-drafts-qa-{version}.yaml").read_text(encoding="utf-8")
        )
        assert {raw["id"] for raw in spec["criteria"]} <= PACKAGE.coverage.declared


def test_every_executed_failure_index_exists_in_the_real_instrument():
    """The two trajectory-shaped executors select mode 1 (flat); everything else mode 0."""
    two_mode = {
        "cr-objectives-non-decreasing-demand",
        "cr-cognitive-demand-rises-across-the-course",
    }
    for criterion_id in PACKAGE.coverage.executes:
        needed = 2 if criterion_id in two_mode else 1
        assert len(_V5_CRITERIA[criterion_id].failure_modes) >= needed


def test_source_config_declares_the_semantic_identity():
    """ADR-0034: models and prompts travel in SOURCE_CONFIG, so the ratification guard
    refuses any of them drifting without a VERSION bump."""
    llm = PACKAGE.source_config["llm"]
    assert set(llm["models"]) == {
        "outcomes_extraction",
        "objectives_classification",
        "concept_trajectory",
        "judge",
        "assessment_mapping",
        "assessment_reach",
    }
    assert llm["temperature"] == 0.0
    # How many answers a judgement is decided by decides WHICH verdict survives, so it is
    # identity too — raising it to 3 is a version bump, not a tuning knob.
    assert llm["samples"] == {"asked": 2, "max": 3}
    # The two v2 exists for: no thinking out loud, and room for the answer if it happens
    # anyway. Both decide what comes back, so both are declared, not left to the wire.
    assert llm["reasoning"] == {"effort": "none"}
    assert llm["maxOutputTokens"] == 8000
    fingerprint = llm["promptsFingerprint"]
    assert isinstance(fingerprint, str) and len(fingerprint) == 64
    from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import prompts

    assert fingerprint == prompts.fingerprint()  # deterministic, computed from the code


# --- the semantic executors: the model supplies data, the code decides ------------------


def test_objectives_observable_verbs(fake_llm):
    spec = _V5_CRITERIA["cr-objectives-observable-verbs"]
    run = PACKAGE.executors["cr-objectives-observable-verbs"]
    data = profile(learning_objectives=["build an API", "understand HTTP deeply"])

    client = fake_llm(objectives=[objectives_json(("apply", True), ("understand", False))])
    verdict = run(spec, data)

    assert not verdict.passed
    assert verdict.failure_mode == spec.failure_modes[0]
    assert verdict.quote == "understand HTTP deeply"  # our text, not the model's
    metric_ids = {m.metric_id for m in verdict.metrics}
    assert metric_ids == {"llm_objectives_classification", "objective_bloom_levels"}
    assert client.calls[0]["temperature"] == 0.0
    # What v1 lost every run to: the thinking is off and the budget has room either way.
    assert client.calls[0]["extra_body"] == {"reasoning": {"effort": "none"}}
    assert client.calls[0]["max_tokens"] == 8000

    tasks.clear_task_cache()
    fake_llm(objectives=[objectives_json(("apply", True), ("analyze", True))])
    assert run(spec, profile(learning_objectives=["build an API", "test the API"])).passed


def test_objectives_non_decreasing_demand_falls_back(fake_llm):
    spec = _V5_CRITERIA["cr-objectives-non-decreasing-demand"]
    run = PACKAGE.executors["cr-objectives-non-decreasing-demand"]
    data = profile(learning_objectives=["analyze systems", "recall terms", "apply patterns"])

    # analyze (4) -> remember (1): a fall of 3, far past the one-level consolidation dip.
    fake_llm(objectives=[objectives_json(("analyze", True), ("remember", True), ("apply", True))])
    verdict = run(spec, data)

    assert not verdict.passed
    assert verdict.failure_mode == spec.failure_modes[0]
    assert verdict.quote == "recall terms"  # the objective where the sequence fell back


def test_objectives_non_decreasing_demand_flat_and_short_sequences(fake_llm):
    spec = _V5_CRITERIA["cr-objectives-non-decreasing-demand"]
    run = PACKAGE.executors["cr-objectives-non-decreasing-demand"]

    flat_texts = [f"understand topic {n}" for n in range(4)]
    fake_llm(objectives=[objectives_json(*[("understand", True)] * 4)])
    flat = run(spec, profile(learning_objectives=flat_texts))
    assert not flat.passed
    assert flat.failure_mode == spec.failure_modes[1]

    # Three flat objectives can be a scope decision: below FLAT_MIN_OBJECTIVES, no verdict
    # of flatness — and a one-level dip is consolidation, not falling back.
    tasks.clear_task_cache()
    fake_llm(objectives=[objectives_json(("apply", True), ("understand", True), ("apply", True))])
    dip = run(spec, profile(learning_objectives=["apply x", "revisit y", "apply z"]))
    assert dip.passed


def test_outcomes_present(fake_llm):
    spec = _V5_CRITERIA["cr-outcomes-present"]
    run = PACKAGE.executors["cr-outcomes-present"]

    fake_llm(outcomes=[outcomes_json((GROUNDED_OUTCOME, "build", True))])
    stated = run(spec, outcomes_profile())
    assert stated.passed
    assert stated.quote == GROUNDED_OUTCOME  # grounding-checked verbatim substring
    assert {m.metric_id: m.value for m in stated.metrics}["stated_outcomes_count"] == 1

    tasks.clear_task_cache()
    fake_llm(outcomes=[outcomes_json()])
    silent = run(spec, outcomes_profile())
    assert not silent.passed
    assert silent.failure_mode == spec.failure_modes[0]
    assert silent.quote in OPENING_BODY.strip()  # the excerpt is verbatim opening text


def test_outcomes_observable_verbs(fake_llm):
    spec = _V5_CRITERIA["cr-outcomes-observable-verbs"]
    run = PACKAGE.executors["cr-outcomes-observable-verbs"]

    internal = "you will be able to build a complete web page"
    fake_llm(
        outcomes=[
            outcomes_json((GROUNDED_OUTCOME, "build", True), (internal[:40], "understand", False))
        ]
    )
    verdict = run(spec, outcomes_profile())
    assert not verdict.passed
    assert verdict.failure_mode == spec.failure_modes[0]


def test_cognitive_demand_trajectory_rules(fake_llm):
    spec = _V5_CRITERIA["cr-cognitive-demand-rises-across-the-course"]
    run = PACKAGE.executors["cr-cognitive-demand-rises-across-the-course"]

    inventory = [lesson(f"0{n}.0", n) for n in range(7)]  # 00.0 .. 06.0; core = 5 lessons
    concepts = [{"lessonId": f"0{n}.0", "concept": f"concept {n}"} for n in range(7)]
    data = profile(lesson_inventory=inventory, lesson_concepts=concepts)
    core_ids = [f"0{n}.0" for n in range(1, 6)]

    # Rising with a one-level consolidation dip: 2,3,2,4,5 — allowed.
    fake_llm(trajectory=[trajectory_json(dict(zip(core_ids, [2, 3, 2, 4, 5], strict=True)))])
    assert run(spec, data).passed

    # Peaks at 4 then works two below what the course already required.
    tasks.clear_task_cache()
    fake_llm(trajectory=[trajectory_json(dict(zip(core_ids, [2, 4, 2, 4, 5], strict=True)))])
    early_peak = run(spec, data)
    assert not early_peak.passed
    assert early_peak.failure_mode == spec.failure_modes[0]
    assert json.loads(early_peak.quote) == {"concept": "concept 3", "lessonId": "03.0"}

    # Five equal core lessons: a list, not a progression.
    tasks.clear_task_cache()
    fake_llm(trajectory=[trajectory_json(dict(zip(core_ids, [3, 3, 3, 3, 3], strict=True)))])
    flat = run(spec, data)
    assert not flat.passed
    assert flat.failure_mode == spec.failure_modes[1]


def test_a_short_course_has_no_trajectory_to_judge(fake_llm):
    spec = _V5_CRITERIA["cr-cognitive-demand-rises-across-the-course"]
    run = PACKAGE.executors["cr-cognitive-demand-rises-across-the-course"]
    client = fake_llm()  # no canned answers: any call would fail the test

    data = profile(
        lesson_inventory=[lesson("00.0", 0), lesson("01.0", 1), lesson("02.0", 2)],
        lesson_concepts=[{"lessonId": "01.0", "concept": "the one core concept"}],
    )
    assert run(spec, data).passed
    assert not client.calls  # one core lesson is a point, not a trajectory — no spend


# --- one extraction, two criteria: the memoization the instrument's pairing expects -----


def test_paired_criteria_share_one_extraction(fake_llm):
    client = fake_llm(outcomes=[outcomes_json((GROUNDED_OUTCOME, "build", True))])
    data = outcomes_profile()

    present = PACKAGE.executors["cr-outcomes-present"](_V5_CRITERIA["cr-outcomes-present"], data)
    verbs = PACKAGE.executors["cr-outcomes-observable-verbs"](
        _V5_CRITERIA["cr-outcomes-observable-verbs"], data
    )

    assert present.passed and verbs.passed
    assert len(client.calls) == 1  # the second criterion read the memoized extraction


# --- the judged criteria: the verdict is the model's, the vocabulary is not -------------


CLOSING_BODY = (
    "# Wrap up\n\nYou have built a page, styled it and published it: the three pieces fit "
    "together into one workflow. Next you will meet JavaScript, which makes it move.\n"
)
GROUNDED_CLOSING = "the three pieces fit together into one workflow"


def verdict_json(*evidence: str, verdict: bool = True, failure_mode: int | None = None) -> str:
    return json.dumps(
        {
            "reason": "what the lesson does, in one sentence",
            "evidence": list(evidence),
            "verdict": verdict,
            "failureMode": failure_mode,
        }
    )


def mapping_json(*entries: tuple[str, str, list[int]]) -> str:
    return json.dumps(
        {
            "objectives": [
                {
                    "objectiveId": objective_id,
                    "reason": "what measures it",
                    "evidence": evidence,
                    "itemIndices": indices,
                }
                for objective_id, evidence, indices in entries
            ]
        }
    )


def reach_json(*entries: tuple[int, list[str]]) -> str:
    return json.dumps(
        {
            "items": [
                {"index": index, "reason": "what it asks", "referencesLessonIds": references}
                for index, references in entries
            ]
        }
    )


def judged_profile() -> ProfileData:
    return profile(
        lesson_inventory=[
            lesson("00.0", 0),
            lesson("01.0", 1),
            lesson("01.1", 2),
            lesson("02.0", 3),
        ],
        lesson_bodies=[
            body("00.0", OPENING_BODY),
            body("01.0", "# Tags\n\nContent."),
            body("01.1", "# More tags\n\nMore content."),
            body("02.0", CLOSING_BODY),
        ],
        declared_objectives=[
            {
                "id": "obj-1",
                "outcome": "The learner can build a page",
                "verifiableBy": "Builds one",
            },
            {"id": "obj-2", "outcome": "The learner can style a page", "verifiableBy": None},
        ],
        lesson_assessment_items=[
            {"lessonId": "02.0", "kind": "quiz", "prompt": "Which tag opens a document?"},
            {"lessonId": "02.0", "kind": "quiz", "prompt": "Build a page from this brief."},
        ],
    )


def run_judged(criterion_id: str, data: ProfileData):
    return PACKAGE.executors[criterion_id](_V5_CRITERIA[criterion_id], data)


def test_the_judge_answers_with_reason_before_verdict():
    """The shape shown to the model puts the reasoning first on purpose: JSON mode emits
    fields as the model writes them, so a verdict-first shape commits before reasoning."""
    from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import prompts

    shape = prompts.JUDGE_USER.template
    assert shape.index('"reason"') < shape.index('"evidence"') < shape.index('"verdict"')


def test_a_judged_criterion_carries_the_model_verdict_and_its_own_quote(fake_llm):
    fake_llm(closing_integrates=[verdict_json(GROUNDED_CLOSING)] * 2)

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed
    assert result.quote == GROUNDED_CLOSING  # what the judge read, not a canonical dump
    assert result.failure_mode is None


def test_the_judge_is_asked_the_instrument_s_own_words(fake_llm):
    """The normative text is never retyped into the assessor: it travels from the spec."""
    client = fake_llm(closing_integrates=[verdict_json(GROUNDED_CLOSING)] * 2)
    spec = _V5_CRITERIA["cr-closing-lesson-integrates"]

    run_judged("cr-closing-lesson-integrates", judged_profile())

    asked = "\n".join(m["content"] for m in client.calls[0]["messages"])
    assert spec.pass_condition.strip() in asked
    for index, mode in enumerate(spec.failure_modes):
        assert f"{index}. {mode}" in asked


def test_a_judged_fail_names_one_of_the_criterion_s_declared_failure_modes(fake_llm):
    fake_llm(
        closing_projects_forward=[
            verdict_json("You have built a page", verdict=False, failure_mode=1)
        ]
        * 2
    )
    spec = _V5_CRITERIA["cr-closing-lesson-projects-forward"]

    result = run_judged("cr-closing-lesson-projects-forward", judged_profile())

    assert not result.passed
    assert result.failure_mode == spec.failure_modes[1]


def test_a_failure_mode_the_criterion_never_declared_is_refused(fake_llm):
    """The judge decides inside a vocabulary it did not write: an out-of-range mode is a
    contract violation like any other, fed back and fatal when persistent."""
    out_of_range = verdict_json("You have built a page", verdict=False, failure_mode=9)
    client = fake_llm(
        closing_projects_forward=[
            out_of_range,
            *([verdict_json("You have built a page", verdict=False, failure_mode=0)] * 2),
        ]
    )

    result = run_judged("cr-closing-lesson-projects-forward", judged_profile())

    assert not result.passed
    assert "not one of the listed failures" in client.calls[1]["messages"][-1]["content"]


def test_an_ungrounded_verdict_quote_is_fed_back(fake_llm):
    client = fake_llm(
        closing_integrates=[
            verdict_json("this sentence is nowhere in the lesson"),
            *([verdict_json(GROUNDED_CLOSING)] * 2),
        ]
    )

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed and result.quote == GROUNDED_CLOSING
    assert "not a passage from the text shown" in client.calls[1]["messages"][-1]["content"]


def test_a_judge_that_never_grounds_its_quote_aborts_the_evaluation(fake_llm):
    """Different wrong answers each time: the schema budget is what runs out."""
    fake_llm(
        closing_integrates=[
            verdict_json("invented one"),
            verdict_json("invented two"),
            verdict_json("invented three"),
        ]
    )

    with pytest.raises(AssessorExecutionError, match="never satisfied the output contract"):
        run_judged("cr-closing-lesson-integrates", judged_profile())


# --- v4: the evidence contract the first calibration runs forced ------------------------


def test_a_judgement_may_rest_on_several_passages(fake_llm):
    """A finding about three places has three pieces of evidence. The first is the result's
    quote — each is a continuous span, so the one a report shows stands on its own — and the
    rest travel as a metric rather than being concatenated into something the course does
    not contain contiguously."""
    fake_llm(
        closing_integrates=[verdict_json(GROUNDED_CLOSING, "You have built a page")] * 2,
    )

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.quote == GROUNDED_CLOSING
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["evidence_closing_integrates"] == [GROUNDED_CLOSING, "You have built a page"]


def test_quotes_stitched_with_an_ellipsis_are_told_what_to_do_instead(fake_llm):
    """The failure that killed a calibration run: every fragment was real, the join was not.
    Told only "not verbatim", the model answered the same thing three times — so the
    feedback now names the rule rather than the symptom."""
    client = fake_llm(
        closing_integrates=[
            verdict_json(f"{GROUNDED_CLOSING} ... You have built a page"),
            *([verdict_json(GROUNDED_CLOSING, "You have built a page")] * 2),
        ]
    )

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed
    feedback = client.calls[1]["messages"][-1]["content"]
    assert "joins separate passages with an ellipsis" in feedback
    assert "split it into several entries" in feedback


def test_a_quote_across_a_line_break_is_grounded_and_stored_as_the_source_writes_it(fake_llm):
    """Whitespace is not content: a model quoting across an indented line renders the indent
    as one space, which is not a finding about the course. What gets stored is the source's
    own span, so a report shows the course's text and not the model's rendering."""
    flattened = "You have built a page, styled it and published it: the three pieces"
    fake_llm(closing_integrates=[verdict_json(flattened.replace(" ", "  "))] * 2)

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed
    assert result.quote == flattened  # the corpus's spacing, not the answer's
    assert result.quote in CLOSING_BODY


def test_repeating_the_same_answer_stops_instead_of_spending_the_budget(fake_llm):
    """At temperature 0 the same conversation gives the same answer, so a model that
    repeats itself after feedback will repeat itself again. Calibration spent three
    identical attempts learning this."""
    client = fake_llm(closing_integrates=[verdict_json("invented")] * 3)

    with pytest.raises(AssessorExecutionError, match="repeated its previous answer verbatim"):
        run_judged("cr-closing-lesson-integrates", judged_profile())

    assert len(client.calls) == 2  # not the full budget of three


def test_arc_character_is_judged_over_both_frame_lessons(fake_llm):
    """Its pass condition asserts about the pair, so it reads both bodies in one question
    rather than sharing the single-lesson judgements — an executor receives only its own
    spec, and a shared question would have to retype a sibling criterion's words."""
    client = fake_llm(arc_character=[verdict_json(GROUNDED_CLOSING)] * 2)

    result = run_judged("cr-arc-character", judged_profile())

    asked = "\n".join(m["content"] for m in client.calls[0]["messages"])
    assert result.passed
    assert GROUNDED_OUTCOME in asked and GROUNDED_CLOSING in asked


# --- v5: markdown is formatting, and a judgement is a vote ------------------------------


def test_a_quote_that_drops_markdown_emphasis_still_grounds(fake_llm):
    """Lesson bodies are markdown and a model quoting `**bold**` drops the markers about as
    often as it keeps them. Byte comparison called that a hallucination; it is formatting.
    What gets stored is still the course's own span, asterisks included."""
    data = judged_profile()
    data.entries["lesson_bodies"].value[3]["body"] = (
        "# Wrap up\n\nYou have built a **complete page**, and the pieces fit together.\n"
    )
    fake_llm(closing_integrates=[verdict_json("You have built a complete page")] * 2)

    result = run_judged("cr-closing-lesson-integrates", data)

    assert result.passed
    # The span runs from the first matched character to the last, so markers INSIDE it are
    # kept and a marker run sitting on the boundary is not. Still verbatim in the source,
    # which is all ADR-0009 asks of a quote.
    assert result.quote == "You have built a **complete page"
    assert result.quote in data.entries["lesson_bodies"].value[3]["body"]


def test_an_answer_cut_off_at_the_budget_is_not_retried(fake_llm):
    """The failure the cap could not prevent: a model repeating one sentence into the
    evidence array runs to the budget, so the JSON never even parses. Feedback cannot correct
    a limit — three such attempts once cost nine minutes and bought nothing."""

    client = fake_llm(closing_integrates=['{"reason": "cut off here'] * 3)
    answer = client.complete
    client.complete = lambda **kwargs: dataclasses.replace(  # type: ignore[method-assign]
        answer(**kwargs), finish_reason="length"
    )

    with pytest.raises(AssessorExecutionError, match="without finishing the answer"):
        run_judged("cr-closing-lesson-integrates", judged_profile())

    assert len(client.calls) == 1  # not the full schema budget


def test_a_judging_call_gets_a_tighter_budget_than_the_extraction_tasks(fake_llm):
    """What an answer may cost bounds degeneration where the evidence cap cannot: the cap is
    checked after the answer arrives, the budget while it is being written."""
    client = fake_llm(closing_integrates=[verdict_json(GROUNDED_CLOSING)] * 2)

    run_judged("cr-closing-lesson-integrates", judged_profile())

    assert client.calls[0]["max_tokens"] == judgments.JUDGE_MAX_OUTPUT_TOKENS
    assert judgments.JUDGE_MAX_OUTPUT_TOKENS < tasks.MAX_OUTPUT_TOKENS


def test_repetition_is_refused_in_every_free_length_array(fake_llm):
    """Repetition is the shape a degenerating answer takes, and it is not confined to
    judging: the reach list once filled with repeated and then invented lesson ids until the
    budget was gone. Refusing duplicates also bounds each list by what the draft contains —
    a mapping cannot name more items than exist, a reach more lessons than the plan has."""
    data = judged_profile()
    fake_llm(
        assessment_reach=[
            reach_json((0, ["00.0", "00.0", "01.0"]), (1, ["01.0"])),
            reach_json((0, ["00.0", "01.0"]), (1, ["01.1"])),
        ],
    )
    client = runtime.get_client()

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", data)

    assert result.passed
    feedback = client.calls[1]["messages"][-1]["content"]
    assert "more than once" in feedback


def test_the_extraction_tasks_are_bounded_too(fake_llm):
    client = fake_llm(
        assessment_reach=[reach_json((0, ["00.0", "01.0"]), (1, ["01.1"]))],
    )

    run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert client.calls[0]["max_tokens"] == judgments.EXTRACTION_MAX_OUTPUT_TOKENS
    assert judgments.EXTRACTION_MAX_OUTPUT_TOKENS < tasks.MAX_OUTPUT_TOKENS


def test_a_runaway_evidence_list_is_refused_with_one_complaint(fake_llm):
    """The degeneration the cap exists for: a real answer looped a nine-quote cycle until
    the token limit cut it off at 191 entries. The complaint that goes back names the rule
    once, rather than once per entry."""
    looping = verdict_json(*([GROUNDED_CLOSING, "You have built a page"] * 40))
    client = fake_llm(
        closing_integrates=[looping, *([verdict_json(GROUNDED_CLOSING)] * 2)],
    )

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed
    feedback = client.calls[1]["messages"][-1]["content"]
    assert f"more than the {judgments.MAX_EVIDENCE} a judgement may rest on" in feedback
    assert feedback.count("- ") == 1  # one complaint, not eighty


def test_the_cap_leaves_room_for_the_widest_answer_seen(fake_llm):
    """Eight passages is what the criterion that reads one block per declared objective
    produces on a real draft; the cap is set above the spread, not against it."""
    wide = verdict_json(
        "Wrap up",
        "You have built a page",
        "styled it and published it",
        GROUNDED_CLOSING,
        "into one workflow",
        "Next you will meet JavaScript",
        "which makes it move",
        "built a page, styled",
    )
    fake_llm(closing_integrates=[wide] * 2)

    assert run_judged("cr-closing-lesson-integrates", judged_profile()).passed


def test_two_agreeing_samples_settle_a_judgement(fake_llm):
    client = fake_llm(closing_integrates=[verdict_json(GROUNDED_CLOSING)] * 2)

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed
    assert len(client.calls) == 2  # no third: two agreeing samples cannot be overturned
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["judgment_agreement_closing_integrates"] == {"samples": 2, "agreed": 2}


def test_a_split_buys_a_third_sample_and_the_majority_wins(fake_llm):
    """The tie-break, and the split reported: a 2-1 is the signal that the criterion never
    said where its threshold is, which is how every under-specified one has been found."""
    client = fake_llm(
        closing_integrates=[
            verdict_json(GROUNDED_CLOSING),
            verdict_json("You have built a page", verdict=False, failure_mode=0),
            verdict_json("the three pieces fit together"),
        ]
    )

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed  # two of three
    assert len(client.calls) == 3
    # the winning side's own words, not a synthesis of the three
    assert result.quote == GROUNDED_CLOSING
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["judgment_agreement_closing_integrates"] == {"samples": 3, "agreed": 2}


def test_a_losing_majority_carries_the_failing_side_s_mode(fake_llm):
    fake_llm(
        closing_projects_forward=[
            verdict_json("You have built a page", verdict=False, failure_mode=1),
            verdict_json("the three pieces fit together"),
            verdict_json("styled it and published it", verdict=False, failure_mode=1),
        ]
    )
    spec = _V5_CRITERIA["cr-closing-lesson-projects-forward"]

    result = run_judged("cr-closing-lesson-projects-forward", judged_profile())

    assert not result.passed
    assert result.failure_mode == spec.failure_modes[1]


def test_the_vote_reports_what_the_whole_judgement_spent(fake_llm):
    fake_llm(closing_integrates=[verdict_json(GROUNDED_CLOSING)] * 2)

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    spent = {m.metric_id: m.value for m in result.metrics}["llm_closing_integrates"]
    assert spent["calls"] == 2  # summed across the samples, not one of them
    assert spent["tokens_in"] == 200


# --- the assessment pair: one mapping, one judgement, two criteria ----------------------


def test_every_objective_has_an_item_is_decided_in_code(fake_llm):
    """The model supplies the mapping; "every objective has at least one" is arithmetic."""
    fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", "Build a page from this brief.", [1]),
                ("obj-2", "Which tag opens a document?", [0]),
            )
        ]
    )

    result = run_judged("cr-every-objective-has-an-assessment-item", judged_profile())

    assert result.passed


def test_an_unmeasured_objective_fails_and_is_named(fake_llm):
    fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", "Build a page from this brief.", [1]),
                ("obj-2", "The learner can style a page", []),
            )
        ]
    )

    result = run_judged("cr-every-objective-has-an-assessment-item", judged_profile())

    assert not result.passed
    assert result.quote == "The learner can style a page"
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["objectives_unmeasured"] == ["obj-2"]
    assert metrics["objectives_measured_count"] == 1


def test_an_item_quoting_html_is_shown_as_the_course_writes_it(fake_llm):
    """The corpus a task demands verbatim quotes from must not be an ENCODED form of the
    text. Serializing it put `class=\\"title\\"` in front of the model, which quoted what it
    could read, and the grounding check refused a correct citation — then the answer repeated
    and the run died on it. One real draft ships an item like this."""
    question = 'If the HTML is <h1 class="title">Hello</h1>, what color will the heading be?'
    data = judged_profile()
    data.entries["lesson_assessment_items"].value[0]["prompt"] = question
    client = fake_llm(
        assessment_mapping=[
            mapping_json(("obj-1", question, [0]), ("obj-2", "The learner can style a page", []))
        ]
    )

    result = run_judged("cr-every-objective-has-an-assessment-item", data)

    assert len(client.calls) == 1  # grounded on the first answer: no retry, no abort
    corpus = "\n".join(m["content"] for m in client.calls[0]["messages"])
    assert question in corpus  # shown unescaped, exactly as the course writes it
    assert not result.passed  # obj-2 has no item, which is this criterion's finding


def test_the_two_assessment_criteria_share_one_mapping(fake_llm):
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", "Build a page from this brief.", [1]),
                ("obj-2", "Which tag opens a document?", [0]),
            )
        ],
        assessment_verification_match=[verdict_json("Build a page from this brief.")] * 2,
    )
    data = judged_profile()

    covered = run_judged("cr-every-objective-has-an-assessment-item", data)
    matched = run_judged("cr-assessment-matches-the-declared-verification", data)

    assert covered.passed and matched.passed
    # one mapping + one judgement: the second criterion did not pay for the mapping again
    assert [call["task_id"] for call in client.calls] == [
        "assessment_mapping",
        # two samples that agree; the mapping was not paid for twice
        "assessment_verification_match",
        "assessment_verification_match",
    ]


def test_the_verification_judge_is_shown_only_the_objectives_it_is_about(fake_llm):
    """Narrowed in code: the criterion excludes objectives with no declared verification,
    and there is nothing to compare for an objective no item bears on."""
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", "Build a page from this brief.", [1]),
                ("obj-2", "Which tag opens a document?", [0]),
            )
        ],
        assessment_verification_match=[verdict_json("Build a page from this brief.")] * 2,
    )

    run_judged("cr-assessment-matches-the-declared-verification", judged_profile())

    asked = "\n".join(m["content"] for m in client.calls[1]["messages"])
    assert "obj-1" in asked and "Builds one" in asked
    assert "obj-2" not in asked  # declares no verification


def test_verification_match_is_vacuous_when_nothing_declares_one(fake_llm):
    data = judged_profile()
    data.entries["declared_objectives"].value[0]["verifiableBy"] = None
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", "Build a page from this brief.", [1]),
                ("obj-2", "Which tag opens a document?", [0]),
            )
        ]
    )

    result = run_judged("cr-assessment-matches-the-declared-verification", data)

    assert result.passed
    assert len(client.calls) == 1  # nothing worth asking a judge
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["verification_pairs_judged"] == 0


# --- assessment reach: extraction, then a count -----------------------------------------


def test_assessment_reach_counts_earlier_lessons_outside_the_item_s_module(fake_llm):
    fake_llm(assessment_reach=[reach_json((0, ["00.0", "01.0"]), (1, ["01.1", "02.0"]))])

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert result.passed  # 00.0, 01.0 and 01.1 are earlier and outside module 02
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["assessment_reaches_back_to"] == ["00.0", "01.0", "01.1"]


def test_assessment_that_only_tests_its_own_module_fails(fake_llm):
    fake_llm(assessment_reach=[reach_json((0, ["02.0"]), (1, ["02.0"]))])

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert not result.passed
    assert (
        result.failure_mode
        == _V5_CRITERIA["cr-assessment-retrieves-earlier-taught-material"].failure_modes[0]
    )


def test_one_earlier_lesson_is_not_enough(fake_llm):
    fake_llm(assessment_reach=[reach_json((0, ["01.0"]), (1, ["02.0"]))])

    assert not run_judged(
        "cr-assessment-retrieves-earlier-taught-material", judged_profile()
    ).passed


def test_a_reach_answer_naming_a_lesson_the_plan_never_declared_is_refused(fake_llm):
    """The closed-set form of the grounding rule: an invented lesson would be counted."""
    client = fake_llm(
        assessment_reach=[
            reach_json((0, ["99.9"]), (1, ["02.0"])),
            reach_json((0, ["00.0", "01.0"]), (1, ["01.1"])),
        ]
    )

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert result.passed
    assert "not a lesson identifier from the plan" in client.calls[1]["messages"][-1]["content"]


# --- the structured-output loop: feedback retry, grounding, abort -----------------------


def test_schema_violations_are_fed_back_and_the_model_recovers(fake_llm):
    client = fake_llm(
        outcomes=["this is not json at all", outcomes_json((GROUNDED_OUTCOME, "build", True))]
    )

    outcomes, usage = tasks.outcomes_extraction(outcomes_profile())

    assert [o.statement for o in outcomes] == [GROUNDED_OUTCOME]
    assert usage.calls == 2
    retry_messages = client.calls[1]["messages"]
    assert retry_messages[-2]["content"] == "this is not json at all"  # its own answer
    assert "not valid JSON" in retry_messages[-1]["content"]  # the validator's feedback


def test_an_ungrounded_quote_is_a_schema_violation(fake_llm):
    hallucinated = outcomes_json(("You will master everything effortlessly", "master", True))
    client = fake_llm(outcomes=[hallucinated, outcomes_json((GROUNDED_OUTCOME, "build", True))])

    outcomes, usage = tasks.outcomes_extraction(outcomes_profile())

    assert usage.calls == 2
    assert "verbatim" in client.calls[1]["messages"][-1]["content"]
    assert outcomes[0].statement == GROUNDED_OUTCOME


def test_a_model_that_never_complies_aborts_the_evaluation(fake_llm):
    fake_llm(outcomes=["nope", "still nope", "never json"])

    with pytest.raises(AssessorExecutionError, match="never satisfied the output contract"):
        tasks.outcomes_extraction(outcomes_profile())


def test_a_dead_transport_aborts_the_evaluation(monkeypatch):
    class DeadClient:
        def complete(self, **kwargs):
            raise LlmTransportError("transport retry budget exhausted after 4 attempts")

    monkeypatch.setattr(runtime, "get_client", lambda: DeadClient())

    with pytest.raises(AssessorExecutionError, match="retry budget exhausted"):
        tasks.outcomes_extraction(outcomes_profile())


# --- the whole package against the frozen LearnpackV2 fixture ---------------------------


def _fixture_profile() -> ProfileData:
    return ProfileData(
        profile_id=uuid4(),
        package_format="LearnpackV2",
        entries={
            requirement_id: ProfileEntryData(
                data_requirement_id=requirement_id,
                provenance=extracted.provenance,
                value=extracted.value,
                quote=extracted.quote,
                locator=extracted.locator,
            )
            for requirement_id, extracted in extract_fixture().items()
        },
    )


def _instrument_spec() -> InstrumentSpec:
    return InstrumentSpec(
        instrument_version_id="course-drafts-qa-v5",
        instrument_id=_V5_SPEC["instrument_id"],
        status="published",
        claims=tuple(ClaimSpec(claim_id=raw["id"]) for raw in _V5_SPEC["claims"]),
        criteria=tuple(_V5_CRITERIA[raw["id"]] for raw in _V5_SPEC["criteria"]),
        bindings=tuple(
            BindingSpec(
                package_format=raw["package_format"],
                task_variables=raw.get("task_variables", {}),
            )
            for raw in _V5_SPEC["bindings"]
        ),
    )


def test_the_package_against_the_frozen_v2_fixture(fake_llm):
    """The exact partition over the real draft, with the fake transport answering what a
    well-behaved model would: the five semantic criteria and the seven judged ones EXECUTE
    (they no longer derive `not_assessed`, which is this artifact's reason to exist), the
    structural results match `drafts-structural`'s pinned run, and the memoization holds —
    ten questions for twelve criteria."""
    fixture = _fixture_profile()
    opening_body, _ = tasks.opening_lesson_body(fixture)
    closing_body, _ = judgments.closing_lesson_body(fixture)
    grounded = next(line for line in opening_body.splitlines() if line.strip()).strip()
    grounded_closing = next(line for line in closing_body.splitlines() if line.strip()).strip()
    objective_count = len(fixture.entries["learning_objectives"].value)
    core_ids = [
        str(lesson["lessonId"])
        for lesson in sorted(
            fixture.entries["lesson_inventory"].value, key=lambda entry: entry["position"]
        )
    ][1:-1]
    rising = [1 + (n * 4) // max(len(core_ids) - 1, 1) for n in range(len(core_ids))]
    objective_ids = [str(o["id"]) for o in fixture.entries["declared_objectives"].value]
    items = list(fixture.entries["lesson_assessment_items"].value)
    first_question = str(items[0]["prompt"])

    client = fake_llm(
        outcomes=[outcomes_json((grounded, "build", True))],
        objectives=[
            objectives_json(
                *[("understand", True), ("apply", True), ("create", True)][:objective_count]
            )
        ],
        trajectory=[trajectory_json(dict(zip(core_ids, rising, strict=True)))],
        opening_connects_backwards=[verdict_json(grounded)] * 2,
        closing_integrates=[verdict_json(grounded_closing)] * 2,
        closing_projects_forward=[verdict_json(grounded_closing)] * 2,
        arc_character=[verdict_json(grounded_closing)] * 2,
        assessment_mapping=[
            mapping_json(*((objective_id, first_question, [0]) for objective_id in objective_ids))
        ],
        assessment_verification_match=[verdict_json(first_question)] * 2,
        # Items 3 and 4 sit in lesson 03.2 and are answered to draw on two earlier lessons
        # from other modules; the rest test only their own.
        assessment_reach=[
            reach_json(
                *(
                    (index, ["00.0", "01.0"] if index >= 3 else [str(item["lessonId"])])
                    for index, item in enumerate(items)
                )
            )
        ],
    )

    outcomes, metrics = derive_and_execute(
        _instrument_spec(), fixture, PACKAGE.coverage, dict(PACKAGE.executors)
    )

    assert len(outcomes) == 29
    by_outcome: dict[str, set[str]] = {}
    for outcome in outcomes:
        by_outcome.setdefault(outcome.outcome, set()).add(outcome.criterion_id)

    assert by_outcome["not_applicable"] == {"cr-prerequisites-declared"}
    assert by_outcome["pass"] == {
        # the structural six, exactly as drafts-structural's pinned run
        "cr-audience-declared",
        "cr-course-has-development",
        "cr-course-opens-with-general-intro",
        "cr-module-structure-well-formed",
        "cr-no-lesson-spikes-in-lexical-load",
        "cr-objectives-min-count",
        # the semantic five, executed at last
        "cr-objectives-observable-verbs",
        "cr-outcomes-present",
        "cr-outcomes-observable-verbs",
        "cr-objectives-non-decreasing-demand",
        "cr-cognitive-demand-rises-across-the-course",
        # the judged seven, executed at last
        "cr-opening-lesson-connects-backwards",
        "cr-closing-lesson-integrates",
        "cr-closing-lesson-projects-forward",
        "cr-arc-character",
        "cr-every-objective-has-an-assessment-item",
        "cr-assessment-matches-the-declared-verification",
        "cr-assessment-retrieves-earlier-taught-material",
    }
    assert by_outcome["not_assessed"] == set(PACKAGE.coverage.abstains)
    assert "fail" not in by_outcome and "no_evidence" not in by_outcome
    assert all(not o.derived and o.quote for o in outcomes if o.outcome == "pass")

    # Twelve criteria, fifteen calls: five judged criteria are voted on twice each, while
    # two share the outcomes extraction and two share the assessment mapping.
    assert len(client.calls) == 15

    metric_values = {m.metric_id: m.value for m in metrics}
    assert metric_values["stated_outcomes_count"] == 1
    assert len(metric_values["objective_bloom_levels"]) == objective_count
    assert metric_values["concept_sophistication_levels"] == rising
    assert metric_values["objectives_unmeasured"] == []
    assert metric_values["assessment_reaches_back_to"] == ["00.0", "01.0"]
    for task_id in ("outcomes_extraction", "objectives_classification", "concept_trajectory"):
        spent = metric_values[f"llm_{task_id}"]
        assert spent["calls"] == 1 and spent["tokens_in"] > 0
    # Every judged criterion travels with the judge's own words about what it read.
    assert metric_values["judgment_arc_character"] == "what the lesson does, in one sentence"


# --- the ratification act ---------------------------------------------------------------


@pytest.fixture
def admin(register_assessor, unique):
    email = f"admin-{unique}@example.com"
    assessor_id = register_assessor(f"user_admin_{unique}", email, "Admin")
    return assessor_id, email


@pytest.fixture
def patched_hybrid_package(unique, monkeypatch):
    """The hybrid package, cloned onto a throwaway lineage (same coverage and config)."""
    name = f"drafts-hybrid-{unique}"
    lineage = f"qa-hybrid-{unique}"
    package = dataclasses.replace(
        PACKAGE,
        name=name,
        instrument_id=lineage,
        source_config={**PACKAGE.source_config, "name": name, "instrumentId": lineage},
    )
    monkeypatch.setitem(AUTOMATED_ASSESSORS, (name, PACKAGE.version), package)
    return package


def hybrid_copy_spec(unique: str) -> dict:
    spec = copy.deepcopy(_V5_SPEC)
    spec["instrument_id"] = f"qa-hybrid-{unique}"
    return spec


def test_ratifying_stores_the_semantic_identity(
    cleanup, unique, namespace, admin, patched_hybrid_package
):
    """The registration act persists SOURCE_CONFIG whole — models, temperature and the
    prompts fingerprint included — which is what arms the drift guard for every later
    ratification (ADR-0034 clause 1)."""
    admin_id, email = admin

    version_id = publish_instrument(cleanup, hybrid_copy_spec(unique), admin_id)
    ratified = run_ratify_assessor(
        patched_hybrid_package.name, patched_hybrid_package.version, version_id, email, []
    )
    assert ratified == 0
    track_automated(cleanup, patched_hybrid_package.name, patched_hybrid_package.version)

    with SessionLocal() as session:
        row = SqlAlchemyAssessorRepository(session).get_automated(
            patched_hybrid_package.name, patched_hybrid_package.version
        )
    assert row is not None
    assert row.source_config == patched_hybrid_package.source_config
    assert row.source_config["llm"]["promptsFingerprint"]
