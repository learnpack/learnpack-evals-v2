"""`drafts-hybrid` v13 — the semantic and judged executors over a fake transport, the
coverage vs the real v7 YAML, the whole package against the frozen LearnpackV2 fixture,
the three-way retry (ADR-0037 §7), and ratification.

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
import re
import threading
import time
from typing import Any
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
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.structured_output import (
    request_structured_output,
)
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform import observability
from app.platform.concurrency import all_at_once
from app.platform.db import SessionLocal
from app.platform.llm import (
    LlmCompletion,
    LlmConfigurationError,
    LlmResponseError,
    LlmTransportError,
)
from tests.conftest import INSTRUMENTS_DIR

PACKAGE = AUTOMATED_ASSESSORS[("drafts-hybrid", "13")]

_SHIPPED_SPEC = yaml.safe_load(
    (INSTRUMENTS_DIR / "course-drafts-qa-v10.yaml").read_text(encoding="utf-8")
)
_SHIPPED_CRITERIA = {
    raw["id"]: CriterionSpec(
        criterion_id=raw["id"],
        pass_condition=raw["pass_condition"],
        failure_modes=tuple(raw["failure_modes"]),
        claim_ids=tuple(raw["claims"]),
        required_data=tuple(raw["requires"]),
        on_missing_evidence=raw.get("on_missing_evidence", "no_evidence"),
        condition=raw.get("condition"),
    )
    for raw in _SHIPPED_SPEC["criteria"]
}


# --- the fake transport (the ADR-0034 seam) --------------------------------------------


class FakeLlmClient:
    """Routes each call to a canned-answer queue: by `task_id` when the test named one,
    otherwise by the task tag in the user prompt (how the v2 extraction tasks are fed).

    Queues hold raw response TEXTS so a test can feed one bad answer and then a good one —
    the feedback-retry loop runs for real against them.

    The concept map is fed a DICT instead, keyed `definitions` and by module id, because its
    calls go out concurrently (v13): a FIFO queue would hand whichever request won the race
    whichever answer happened to be first, and the test would pass or fail by scheduling. The
    key is read off the prompt, so each call gets the answer written for it however the threads
    interleave. `calls` is appended under a lock for the same reason — the count is an
    assertion in several tests.
    """

    def __init__(
        self,
        outcomes: list[str] | None = None,
        objectives: list[str] | None = None,
        trajectory: list[str] | None = None,
        concept_map: dict[str, str] | None = None,
        **by_task: list[str],
    ) -> None:
        self._queues = {
            "<lesson>": list(outcomes or []),
            "<objectives>": list(objectives or []),
            "<plan>": list(trajectory or []),
        }
        self._by_task = {task_id: list(answers) for task_id, answers in by_task.items()}
        self._concept_map = dict(concept_map or {})
        self._lock = threading.Lock()
        self.calls: list[dict] = []

    @staticmethod
    def _concept_map_key(prompt_text: str) -> str:
        """Which of the two passes this is, and for which module — read off the prompt the
        way a reader would: the definitions pass shows the whole course, a usage pass shows
        one module and names its lessons."""
        if "<course>" in prompt_text:
            return "definitions"
        shown = re.findall(r"===== LESSON (\d+)\.", prompt_text)
        assert shown, "a usage call must show at least one lesson"
        return shown[0]

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
        with self._lock:
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
        prompt_text = "\n".join(m["content"] for m in messages)
        if task_id == "concept_map" and self._concept_map:
            key = self._concept_map_key(prompt_text)
            assert key in self._concept_map, f"fake transport has no answer for {key!r}"
            return LlmCompletion(
                text=self._concept_map[key], model=model, tokens_in=100, tokens_out=40, latency_ms=7
            )
        if task_id in self._by_task:
            with self._lock:
                queue = self._by_task[task_id]
                assert queue, f"fake transport has no answer left for task {task_id!r}"
                answer = queue.pop(0)
            return LlmCompletion(
                text=answer, model=model, tokens_in=100, tokens_out=40, latency_ms=7
            )
        for tag, queue in self._queues.items():
            if tag in prompt_text:
                assert queue, f"fake transport has no answer left for {tag}"
                return LlmCompletion(
                    text=queue.pop(0), model=model, tokens_in=100, tokens_out=40, latency_ms=7
                )
        raise AssertionError(f"no queue for task {task_id!r} and no task tag in the prompt")


@pytest.fixture(autouse=True)
def isolated_task_cache():
    """Each test evaluates in its own memoization scope, like each evaluation does."""
    with drafts_hybrid.cache_scope():
        yield


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


def concept_map_json(*entries: tuple[int, str, list[tuple[str, str]]]) -> str:
    """One pass's answer: (concept index, group, [(lesson id, quote)]) per entry.

    Entries for one concept merge, so a test writes one line per group and the shape the model
    is asked for — one object per concept carrying several groups — comes out of it.
    """
    by_concept: dict[int, dict] = {}
    for index, group, appearances in entries:
        entry = by_concept.setdefault(index, {"conceptIndex": index})
        entry.setdefault(group, []).extend(
            {"lessonId": lesson_id, "quote": quote} for lesson_id, quote in appearances
        )
    return json.dumps({"concepts": list(by_concept.values())})


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


def test_coverage_decides_every_criterion_of_the_shipped_instrument():
    """Every criterion of the version this artifact is written against is decided, and nothing
    is decided twice (ADR-0018).

    A SUPERSET rather than an equality, and v9 is why. Until then every revision of this
    lineage had only ever added ids or reworded conditions, so "declares exactly the shipped
    instrument's criteria" and "declares every criterion of every version" were the same set.
    v9 RETIRES `cr-later-lessons-apply-earlier-concepts`, replacing it with two, so the
    artifact must go on deciding an id no current version declares — otherwise it stops being
    able to ratify v2 through v8, which are the versions the measured studies pin.
    """
    shipped = {raw["id"] for raw in _SHIPPED_SPEC["criteria"]}
    assert shipped <= PACKAGE.coverage.declared
    assert not (PACKAGE.coverage.executes & set(PACKAGE.coverage.abstains))
    assert PACKAGE.instrument_id == _SHIPPED_SPEC["instrument_id"]
    assert len(PACKAGE.coverage.executes) == 21


def test_coverage_declares_nothing_no_version_of_the_lineage_asks_for():
    """The other half of the superset: an id decided here must be an id some version declares.

    Without it, `declared` could accumulate typos and retired ids forever and the test above
    would never notice.
    """
    lineage = set()
    for spec_file in INSTRUMENTS_DIR.glob("course-drafts-qa-v*.yaml"):
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        lineage |= {raw["id"] for raw in spec["criteria"]}
    orphans = PACKAGE.coverage.declared - lineage
    assert not orphans, f"decided by the artifact but declared by no version: {sorted(orphans)}"


def test_coverage_also_decides_every_criterion_of_the_lineages_other_versions():
    """Criterion ids are stable across the lineage — every revision since v2 changed a
    `requires` or a pass condition and none touched an id — so the one artifact can ratify
    any published version (ADR-0019).

    Read off disk rather than from a list of version numbers: versions are cheap and are
    deleted when nothing reads them any more, and a hardcoded list turns that into a failing
    test about a file instead of a claim about coverage.
    """
    others = sorted(INSTRUMENTS_DIR.glob("course-drafts-qa-v*.yaml"))
    assert len(others) > 1, "the lineage should have more than the version this assessor pins"

    for spec_file in others:
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        undecided = {raw["id"] for raw in spec["criteria"]} - PACKAGE.coverage.declared
        assert not undecided, f"{spec_file.name}: {', '.join(sorted(undecided))}"


def test_every_executed_failure_index_exists_in_the_real_instrument():
    """Most executors select mode 0; these select further along the criterion's own list, so
    the list has to be long enough. The within-module one reaches mode 2 — a stretch of
    consecutive lessons — which is the highest index any executor here selects."""
    modes_needed = {
        "cr-objectives-non-decreasing-demand": 2,
        "cr-cognitive-demand-rises-across-the-course": 2,
        "cr-modules-build-on-earlier-modules": 2,
        "cr-lessons-build-within-their-module": 3,
    }
    for criterion_id in PACKAGE.coverage.executes:
        needed = modes_needed.get(criterion_id, 1)
        assert len(_SHIPPED_CRITERIA[criterion_id].failure_modes) >= needed


def test_source_config_declares_the_semantic_identity():
    """ADR-0034: models and prompts travel in SOURCE_CONFIG, so the ratification guard
    refuses any of them drifting without a VERSION bump."""
    llm = PACKAGE.source_config["llm"]
    assert set(llm["models"]) == {
        "outcomes_extraction",
        "objectives_classification",
        "concept_trajectory",
        "concept_map",
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
    # Both disable fields, on purpose (v7): OpenRouter documents `effort` for other model
    # families, and the upstreams that reasoned anyway under v6 may only translate
    # `enabled`. Saying it both ways is identity — it decides what is billed and returned.
    assert llm["reasoning"] == {"effort": "none", "enabled": False}
    assert llm["maxOutputTokens"] == 8000
    # The one task that contradicts both of those, declared apart so the config cannot read
    # as uniform when it is not (v13). Its effort is what the definitions pass needs — at
    # medium it drifted to 14–15 of 18 against readers where high scored 17 of 17 — and its
    # budget is four times the rest because a reasoning model bills its thinking against it.
    assert llm["conceptMap"] == {
        "reasoning": {"effort": "high"},
        "maxOutputTokens": 32000,
        "maxLessonsPerGroup": 6,
    }
    # How a failing conversation is retried decides which answer finally arrives, so the
    # clean-retry allowance is identity too (ADR-0037 §7). Budget joined in v8: a
    # length-cut runaway is deterministic per PROVIDER, and a fresh conversation re-rolls
    # the router's provider draw.
    assert llm["cleanRetries"] == {"max": 1, "kinds": ["degeneration", "budget"]}
    # Which upstreams may not serve a call decides which judge answers it (ADR-0038):
    # the pool is identity, so the list is declared and guarded like the model ids.
    assert llm["deniedProviders"] == ["sail-research", "atlas-cloud"]
    fingerprint = llm["promptsFingerprint"]
    assert isinstance(fingerprint, str) and len(fingerprint) == 64
    from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import prompts

    assert fingerprint == prompts.fingerprint()  # deterministic, computed from the code


# --- the semantic executors: the model supplies data, the code decides ------------------


def test_objectives_observable_verbs(fake_llm):
    spec = _SHIPPED_CRITERIA["cr-objectives-observable-verbs"]
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
    assert client.calls[0]["extra_body"] == {
        "reasoning": {"effort": "none", "enabled": False},
        # The deny-list reaches the wire on every call (ADR-0038).
        "provider": {"ignore": ["sail-research", "atlas-cloud"]},
    }
    assert client.calls[0]["max_tokens"] == 8000

    tasks.clear_task_cache()
    fake_llm(objectives=[objectives_json(("apply", True), ("analyze", True))])
    assert run(spec, profile(learning_objectives=["build an API", "test the API"])).passed


def test_objectives_non_decreasing_demand_falls_back(fake_llm):
    spec = _SHIPPED_CRITERIA["cr-objectives-non-decreasing-demand"]
    run = PACKAGE.executors["cr-objectives-non-decreasing-demand"]
    data = profile(learning_objectives=["analyze systems", "recall terms", "apply patterns"])

    # analyze (4) -> remember (1): a fall of 3, far past the one-level consolidation dip.
    fake_llm(objectives=[objectives_json(("analyze", True), ("remember", True), ("apply", True))])
    verdict = run(spec, data)

    assert not verdict.passed
    assert verdict.failure_mode == spec.failure_modes[0]
    assert verdict.quote == "recall terms"  # the objective where the sequence fell back


def test_objectives_non_decreasing_demand_flat_and_short_sequences(fake_llm):
    spec = _SHIPPED_CRITERIA["cr-objectives-non-decreasing-demand"]
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
    spec = _SHIPPED_CRITERIA["cr-outcomes-present"]
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
    spec = _SHIPPED_CRITERIA["cr-outcomes-observable-verbs"]
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
    spec = _SHIPPED_CRITERIA["cr-cognitive-demand-rises-across-the-course"]
    run = PACKAGE.executors["cr-cognitive-demand-rises-across-the-course"]

    inventory = [lesson(f"0{n}.0", n) for n in range(7)]  # 00.0 .. 06.0; core = 5 lessons
    concepts = [{"lessonId": f"0{n}.0", "concepts": [f"concept {n}"]} for n in range(7)]
    data = profile(lesson_inventory=inventory, lesson_concept_coverage=concepts)
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
    assert json.loads(early_peak.quote) == {"concepts": ["concept 3"], "lessonId": "03.0"}

    # Five equal core lessons: a list, not a progression.
    tasks.clear_task_cache()
    fake_llm(trajectory=[trajectory_json(dict(zip(core_ids, [3, 3, 3, 3, 3], strict=True)))])
    flat = run(spec, data)
    assert not flat.passed
    assert flat.failure_mode == spec.failure_modes[1]


def test_a_short_course_has_no_trajectory_to_judge(fake_llm):
    spec = _SHIPPED_CRITERIA["cr-cognitive-demand-rises-across-the-course"]
    run = PACKAGE.executors["cr-cognitive-demand-rises-across-the-course"]
    client = fake_llm()  # no canned answers: any call would fail the test

    data = profile(
        lesson_inventory=[lesson("00.0", 0), lesson("01.0", 1), lesson("02.0", 2)],
        lesson_concept_coverage=[{"lessonId": "01.0", "concepts": ["the one core concept"]}],
    )
    assert run(spec, data).passed
    assert not client.calls  # one core lesson is a point, not a trajectory — no spend


# --- the continuity criteria: one concept map, two verdicts (v13) -----------------------
#
# The map's shape makes these readable without a fixture: every lesson declares exactly one
# concept, named after itself, so concept index N is lesson N's concept and a test says "01.1
# works with what 01.0 introduced" in those words. The queue the fake serves is ordered the way
# the task asks: the definitions pass over the whole course, then one usage call per module in
# identifier order.


def continuity_quote(lesson_id: str) -> str:
    return f"Lesson {lesson_id} works through the material in a full sentence."


def continuity_profile(*lesson_ids: str) -> ProfileData:
    return profile(
        lesson_inventory=[lesson(lid, index) for index, lid in enumerate(lesson_ids)],
        lesson_bodies=[
            body(lid, f"# Heading {lid}\n\n{continuity_quote(lid)}\n") for lid in lesson_ids
        ],
        lesson_concept_coverage=[
            {"lessonId": lid, "concepts": [f"concept of {lid}"]} for lid in lesson_ids
        ],
    )


def continuity_answers(
    lesson_ids: tuple[str, ...],
    defines: dict[str, str],
    usage: dict[str, tuple[tuple[str, str, str], ...]],
) -> dict[str, str]:
    """One answer per call, keyed the way the fake routes them: `defines` maps a concept
    (named by its owning lesson) to the lesson that states it; `usage` maps a module to
    (lesson, concept owner, group) triples."""
    index_of = {lid: index for index, lid in enumerate(lesson_ids)}
    modules = sorted({lid.split(".")[0] for lid in lesson_ids})
    answers = {
        "definitions": concept_map_json(
            *(
                (index_of[owner], "defines", [(stated_in, continuity_quote(stated_in))])
                for owner, stated_in in defines.items()
            )
        )
    }
    answers.update(
        {
            module: concept_map_json(
                *(
                    (index_of[owner], group, [(lesson_id, continuity_quote(lesson_id))])
                    for lesson_id, owner, group in usage.get(module, ())
                )
            )
            for module in modules
        }
    )
    return answers


def run_continuity(criterion_id: str, data: ProfileData):
    return PACKAGE.executors[criterion_id](_SHIPPED_CRITERIA[criterion_id], data)


WITHIN = "cr-lessons-build-within-their-module"
ACROSS = "cr-modules-build-on-earlier-modules"


def test_a_module_whose_later_lessons_work_with_its_earlier_ones_passes(fake_llm):
    lessons = ("00.0", "01.0", "01.1", "02.0", "02.1")
    fake_llm(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            usage={
                "01": (("01.1", "01.0", "uses_as_known"),),
                "02": (("02.1", "02.0", "assessed"),),
            },
        )
    )

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    assert verdict.passed
    # The passing quote is the course's own text, at the first place the criterion found it.
    assert verdict.quote == continuity_quote("01.1")
    metrics = {m.metric_id: m.value for m in verdict.metrics}
    assert metrics["module_internal_build"] == {"of": 2, "built": 2}
    assert metrics["concept_map_coverage"]["dropped"] == 0
    assert metrics["llm_concept_map"]["calls"] == 4  # definitions + three modules


def test_lessons_that_sit_side_by_side_fail(fake_llm):
    lessons = ("00.0", "01.0", "01.1", "02.0", "02.1")
    fake_llm(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            # Each interior lesson names its module's earlier concept and does nothing with it.
            usage={
                "01": (("01.1", "01.0", "mentions"),),
                "02": (("02.1", "02.0", "mentions"),),
            },
        )
    )

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    assert not verdict.passed
    assert verdict.failure_mode == _SHIPPED_CRITERIA[WITHIN].failure_modes[0]
    assert verdict.quote.startswith("# Heading 01.1")  # the first lesson that failed


def test_saying_again_what_the_module_taught_is_not_building_on_it(fake_llm):
    """The asymmetry the vocabulary exists for: a lesson may add to a concept later, and may
    not state again what it is. Re-defining is the course starting over."""
    lessons = ("00.0", "01.0", "01.1", "02.0", "02.1")
    answers = continuity_answers(
        lessons,
        defines={lid: lid for lid in lessons},
        usage={"02": (("02.1", "02.0", "develops"),)},
    )
    # 01.1 states 01.0's concept a second time. 01.0 states it first, so 01.0 is the
    # introduction and 01.1 is the course saying again what it had already said.
    answers["definitions"] = concept_map_json(
        *((index, "defines", [(lid, continuity_quote(lid))]) for index, lid in enumerate(lessons)),
        (1, "defines", [("01.1", continuity_quote("01.1"))]),
    )
    fake_llm(concept_map=answers)

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    assert not verdict.passed
    assert verdict.failure_mode == _SHIPPED_CRITERIA[WITHIN].failure_modes[1]
    assert verdict.quote == continuity_quote("01.1")  # the restatement itself
    metrics = {m.metric_id: m.value for m in verdict.metrics}
    assert metrics["module_internal_build"] == {"of": 2, "built": 1}


def test_two_consecutive_lessons_that_build_on_nothing_fail_a_passing_ratio(fake_llm):
    """Both halves of the pass condition are load-bearing: four of six meets two thirds
    exactly, and the criterion still fails because two consecutive lessons built on nothing."""
    lessons = ("00.0", "01.0", "01.1", "01.2", "01.3", "01.4", "01.5", "01.6")
    fake_llm(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            usage={
                "01": (
                    ("01.1", "01.0", "uses_as_known"),
                    ("01.2", "01.0", "uses_as_known"),
                    # 01.3 and 01.4 work with nothing their module introduced.
                    ("01.5", "01.0", "uses_as_known"),
                    ("01.6", "01.0", "uses_as_known"),
                ),
            },
        )
    )

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    metrics = {m.metric_id: m.value for m in verdict.metrics}
    assert metrics["module_internal_build"] == {"of": 6, "built": 4}  # exactly two thirds
    assert not verdict.passed
    assert verdict.failure_mode == _SHIPPED_CRITERIA[WITHIN].failure_modes[2]


def test_modules_of_one_lesson_contribute_no_denominator(fake_llm):
    """A module with no interior cannot fail to build across it — the criterion's own words,
    and the alternative explanation its claim carries."""
    lessons = ("00.0", "01.0", "02.0", "03.0")
    fake_llm(
        concept_map=continuity_answers(lessons, defines={lid: lid for lid in lessons}, usage={})
    )

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    assert verdict.passed
    assert {m.metric_id: m.value for m in verdict.metrics}["module_internal_build"]["of"] == 0


def test_the_introduction_is_the_earliest_lesson_that_states_a_concept(fake_llm):
    """The deterministic anchor: a concept two lessons state is introduced by the first, so a
    lesson between them is building on it rather than preceding it."""
    lessons = ("00.0", "01.0", "01.1", "01.2")
    answers = continuity_answers(
        lessons,
        defines={lid: lid for lid in lessons},
        usage={"01": (("01.1", "01.0", "uses_as_known"), ("01.2", "01.0", "develops"))},
    )
    # 01.2 states 01.0's concept as well; `min(position)` still puts the introduction at 01.0.
    answers["definitions"] = concept_map_json(
        *((index, "defines", [(lid, continuity_quote(lid))]) for index, lid in enumerate(lessons)),
        (1, "defines", [("01.2", continuity_quote("01.2"))]),
    )
    fake_llm(concept_map=answers)

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    assert verdict.passed
    assert {m.metric_id: m.value for m in verdict.metrics}["module_internal_build"] == {
        "of": 2,
        "built": 2,
    }


def test_later_modules_that_work_with_earlier_ones_pass(fake_llm):
    lessons = ("00.0", "01.0", "02.0", "03.0")
    fake_llm(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            usage={
                "02": (("02.0", "01.0", "uses_as_known"),),
                "03": (("03.0", "01.0", "assessed"),),
            },
        )
    )

    verdict = run_continuity(ACROSS, continuity_profile(*lessons))

    assert verdict.passed
    # Module 00 is the opening slot, so the population is 02 and 03 — the thematic modules
    # after the first one.
    assert {m.metric_id: m.value for m in verdict.metrics}["cross_module_build"] == {
        "of": 2,
        "built": 2,
    }


def test_modules_that_only_refer_back_fail_as_such(fake_llm):
    """The second failure mode the criterion declares, and it is a different finding from a
    course whose modules carry nothing back at all."""
    lessons = ("00.0", "01.0", "02.0", "03.0")
    fake_llm(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            usage={
                "02": (("02.0", "01.0", "mentions"),),
                "03": (("03.0", "01.0", "mentions"),),
            },
        )
    )

    verdict = run_continuity(ACROSS, continuity_profile(*lessons))

    assert not verdict.passed
    assert verdict.failure_mode == _SHIPPED_CRITERIA[ACROSS].failure_modes[1]
    assert verdict.quote == continuity_quote("02.0")


def test_a_usage_call_may_not_name_a_lesson_it_was_not_shown(fake_llm):
    """The fan-out's honesty guard: a module's call sees one module, so a row about another
    module's lesson is dropped rather than trusted — and the loss is reported, not swallowed."""
    lessons = ("00.0", "01.0", "01.1", "02.0", "02.1")
    answers = continuity_answers(
        lessons,
        defines={lid: lid for lid in lessons},
        usage={"01": (("01.1", "01.0", "uses_as_known"),)},
    )
    # The module 02 call answers about a lesson of module 01.
    answers["02"] = concept_map_json(
        (1, "uses_as_known", [("01.1", continuity_quote("01.1"))]),
    )
    fake_llm(concept_map=answers)

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    metrics = {m.metric_id: m.value for m in verdict.metrics}
    assert metrics["concept_map_coverage"]["dropped"] == 1
    assert metrics["module_internal_build"] == {"of": 2, "built": 1}


def test_the_continuity_pair_share_one_concept_map(fake_llm):
    """The reason the map is one task: two criteria, one fan-out."""
    lessons = ("00.0", "01.0", "01.1", "02.0", "02.1")
    client = fake_llm(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            usage={
                "01": (("01.1", "01.0", "uses_as_known"),),
                "02": (("02.1", "02.0", "uses_as_known"), ("02.0", "01.0", "uses_as_known")),
            },
        )
    )
    data = continuity_profile(*lessons)

    within = run_continuity(WITHIN, data)
    across = run_continuity(ACROSS, data)

    assert within.passed and across.passed
    assert len(client.calls) == 4  # definitions + three modules, asked once for both


def test_the_map_calls_go_out_together(monkeypatch):
    """The fan-out is not an optimization detail, it is what makes this task affordable: over
    one real draft the map was 84 % of an evaluation's wall clock, seven serial calls totalling
    517 seconds where the slowest single one took 114.

    Pinned with a barrier rather than a stopwatch. Every call waits for all of them to arrive,
    so a serial implementation cannot get past the first — no timing threshold to tune, and no
    flake on a slow machine.
    """
    lessons = ("00.0", "01.0", "01.1", "02.0", "02.1")
    inner = FakeLlmClient(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            usage={"01": (("01.1", "01.0", "uses_as_known"),)},
        )
    )
    barrier = threading.Barrier(4, timeout=20)  # the definitions pass plus three modules

    class Barriered:
        def complete(self, **kwargs):
            if kwargs.get("task_id") == "concept_map":
                barrier.wait()
            return inner.complete(**kwargs)

    monkeypatch.setattr(runtime, "get_client", lambda: Barriered())

    verdict = run_continuity(WITHIN, continuity_profile(*lessons))

    assert not verdict.passed  # only one of the two interior lessons builds; the verdict is
    assert len(inner.calls) == 4  # incidental here — what is pinned is that all four ran at once


def test_the_fan_out_is_observable(monkeypatch):
    """A call made on a worker thread still reaches the caller's sink.

    The trace sink is a `ContextVar`, and a fresh thread starts with an empty context, so the
    first fan-out emitted nothing at all: the evaluation's most expensive task left no record
    of what it asked or what came back. That is the one thing the calibration runbook cannot
    work without, and it failed silently — the run looked fine and the trace was simply short.
    """
    lessons = ("00.0", "01.0", "01.1", "02.0", "02.1")
    inner = FakeLlmClient(
        concept_map=continuity_answers(
            lessons,
            defines={lid: lid for lid in lessons},
            usage={"01": (("01.1", "01.0", "uses_as_known"),)},
        )
    )

    class Emitting:
        """The fake, doing the one thing the real transport does besides answering."""

        def complete(self, **kwargs):
            completion = inner.complete(**kwargs)
            observability.emit(
                observability.LlmCall(
                    task_id=kwargs.get("task_id"),
                    attempt=1,
                    model_requested=kwargs["model"],
                    messages=(),
                    latency_ms=1,
                )
            )
            return completion

    monkeypatch.setattr(runtime, "get_client", lambda: Emitting())
    recorded, sink = observability.recording()

    with observability.collecting(sink):
        run_continuity(WITHIN, continuity_profile(*lessons))

    assert sum(1 for call in recorded if call.task_id == "concept_map") == 4


def test_a_course_with_no_declared_concept_is_not_asked_about(fake_llm):
    client = fake_llm()  # no canned answers: any call would fail the test
    data = profile(
        lesson_inventory=[lesson("00.0", 0), lesson("01.0", 1), lesson("01.1", 2)],
        lesson_bodies=[body(lid, "# Heading\n\nText.") for lid in ("00.0", "01.0", "01.1")],
        lesson_concept_coverage=[{"lessonId": "01.0", "concepts": []}],
    )

    assert run_continuity(WITHIN, data).passed
    assert not client.calls


# --- one extraction, two criteria: the memoization the instrument's pairing expects -----


def test_paired_criteria_share_one_extraction(fake_llm):
    client = fake_llm(outcomes=[outcomes_json((GROUNDED_OUTCOME, "build", True))])
    data = outcomes_profile()

    present = PACKAGE.executors["cr-outcomes-present"](
        _SHIPPED_CRITERIA["cr-outcomes-present"], data
    )
    verbs = PACKAGE.executors["cr-outcomes-observable-verbs"](
        _SHIPPED_CRITERIA["cr-outcomes-observable-verbs"], data
    )

    assert present.passed and verbs.passed
    assert len(client.calls) == 1  # the second criterion read the memoized extraction


def test_paired_criteria_asking_at_the_same_moment_still_pay_once(monkeypatch):
    """Once means once when the two arrive together, which is how the derivation now runs
    them (ADR-0048).

    "Look it up, run it if missing" is two steps, and the second criterion used to arrive
    between them: it found nothing remembered — the answer was still on the wire — and asked
    the same question again. The window is forced open here rather than hoped for: the second
    criterion does not start looking until the first is already inside the call.
    """
    data = outcomes_profile()
    inner = FakeLlmClient(outcomes=[outcomes_json((GROUNDED_OUTCOME, "build", True))] * 2)
    asking = threading.Event()

    class Slow:
        def complete(self, **kwargs):
            asking.set()  # the first criterion is on the wire, and stays there a while
            time.sleep(0.2)
            return inner.complete(**kwargs)

    monkeypatch.setattr(runtime, "get_client", lambda: Slow())

    def ask(criterion_id: str):
        if criterion_id == "cr-outcomes-observable-verbs":
            assert asking.wait(timeout=20)
        return PACKAGE.executors[criterion_id](_SHIPPED_CRITERIA[criterion_id], data)

    present, verbs = all_at_once(ask, ["cr-outcomes-present", "cr-outcomes-observable-verbs"])

    assert present.passed and verbs.passed
    assert len(inner.calls) == 1  # the second waited for the first's answer instead of buying one


def test_two_evaluations_of_one_profile_each_ask_for_themselves(fake_llm):
    """The other half of the memoization contract: sharing is within ONE evaluation.

    Repeats over the same content are how a judge's variance gets measured, so a second run
    reading the first one's answer would not be a second sample — it would be one answer
    counted twice, silently, with an empty trace and a spend it never paid.
    """
    client = fake_llm(
        outcomes=[
            outcomes_json((GROUNDED_OUTCOME, "build", True)),
            outcomes_json((GROUNDED_OUTCOME, "build", True)),
        ]
    )
    data = outcomes_profile()
    spec = _SHIPPED_CRITERIA["cr-outcomes-present"]

    for _ in range(2):
        with drafts_hybrid.cache_scope():
            assert PACKAGE.executors["cr-outcomes-present"](spec, data).passed

    assert len(client.calls) == 2


def test_concurrent_evaluations_do_not_read_each_others_answers(fake_llm):
    """Two workers, one profile: each pays for its own answer. Without a scope per thread
    the batch would silently collapse repeats into one measurement — and the caches used to
    be one dict per process, which is exactly what a parallel batch would have shared."""
    client = fake_llm(
        outcomes=[
            outcomes_json((GROUNDED_OUTCOME, "build", True)),
            outcomes_json((GROUNDED_OUTCOME, "build", True)),
        ]
    )
    data = outcomes_profile()
    spec = _SHIPPED_CRITERIA["cr-outcomes-present"]
    passed: list[bool] = []
    barrier = threading.Barrier(2)

    def evaluate() -> None:
        with drafts_hybrid.cache_scope():
            barrier.wait(timeout=5)  # both inside their scopes before either asks
            passed.append(PACKAGE.executors["cr-outcomes-present"](spec, data).passed)

    threads = [threading.Thread(target=evaluate) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert passed == [True, True]
    assert len(client.calls) == 2


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


def mapping_json(*entries: tuple[str, list[int]]) -> str:
    """The mapping's answer since v12: which tasks bear on each objective, by index. No
    quote — the corpus is a template and asking a model to transcribe one of its lines is
    what made it splice two of them together."""
    return json.dumps(
        {
            "objectives": [
                {
                    "objectiveId": objective_id,
                    "reason": "what measures it",
                    "taskIndices": indices,
                }
                for objective_id, indices in entries
            ]
        }
    )


VERIFICATION = "cr-assessment-matches-the-declared-verification"


def _feedback_of(client) -> str:
    """What the validator sent back — the last message of the first call that carries one."""
    return next(
        call["messages"][-1]["content"] for call in client.calls if len(call["messages"]) > 2
    )


def verification_json(*entries: tuple[Any, ...]) -> str:
    """The per-objective judge's answer (v12): one entry per objective, the tasks that decide
    it cited by number, and the criterion's own verdict left to code.

    An entry is `(objectiveId, taskNumbers, satisfied)`, plus the declared failure mode when
    it is not satisfied — mode 0 by default, since most criteria declare more than one and
    which one a failing objective shows is the model's to name."""
    objectives = []
    for objective_id, numbers, satisfied, *mode in entries:
        objectives.append(
            {
                "objectiveId": objective_id,
                "reason": "what the tasks offered for it ask for",
                "taskNumbers": numbers,
                "satisfied": satisfied,
                "failureMode": None if satisfied else (mode[0] if mode else 0),
            }
        )
    return json.dumps({"objectives": objectives})


def reach_json(*entries: tuple[int, list[str]]) -> str:
    return json.dumps(
        {
            "tasks": [
                {"index": index, "reason": "what it asks", "referencesLessonIds": references}
                for index, references in entries
            ]
        }
    )


PROPOSED_EXERCISE = (
    "In this exercise, the student writes a page with a heading and a link,\n"
    "reusing the tags introduced earlier."
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
        # What the draft offers, mixed on purpose: two tasks it delivers and one it only
        # proposes, which is the shape every real draft of this format has (ADR-0046).
        assessment_offerings=[
            {
                "lessonId": "02.0",
                "status": "delivered",
                "kind": "multipleChoice",
                "prompt": "Which tag opens a document?",
            },
            {
                "lessonId": "02.0",
                "status": "delivered",
                "kind": "multipleChoice",
                "prompt": "Build a page from this brief.",
            },
            {
                "lessonId": "01.1",
                "status": "proposed",
                "kind": "codeChallenge",
                "prompt": PROPOSED_EXERCISE,
            },
        ],
    )


def run_judged(criterion_id: str, data: ProfileData):
    return PACKAGE.executors[criterion_id](_SHIPPED_CRITERIA[criterion_id], data)


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
    spec = _SHIPPED_CRITERIA["cr-closing-lesson-integrates"]

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
    spec = _SHIPPED_CRITERIA["cr-closing-lesson-projects-forward"]

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


def test_repeating_the_same_answer_stops_the_conversation_and_a_second_degeneration_raises(
    fake_llm,
):
    """At temperature 0 the same conversation gives the same answer, so a model that
    repeats itself after feedback will repeat itself again — the conversation stops at two
    calls, not the schema budget of three. Since v6 a degeneration buys ONE clean
    conversation (ADR-0037 §7); when that one degenerates identically, it is the poison
    case and raises."""
    client = fake_llm(closing_integrates=[verdict_json("invented")] * 4)

    with pytest.raises(AssessorExecutionError, match="repeated its previous answer verbatim") as e:
        run_judged("cr-closing-lesson-integrates", judged_profile())

    assert e.value.kind == "degeneration"
    assert len(client.calls) == 4  # two conversations of two calls each, never three


def test_a_degeneration_buys_one_clean_conversation_and_the_verdict_counts_its_cost(fake_llm):
    """The broken round is never fed back — the retry conversation starts from scratch —
    and the verdict that needed it reports `clean_retries`, because answers that arrive
    after a retry are a shifted population (ADR-0037 §7)."""
    client = fake_llm(
        closing_integrates=[
            verdict_json("invented"),  # grounding violation, fed back
            verdict_json("invented"),  # identical -> degeneration -> clean retry
            verdict_json(GROUNDED_CLOSING),  # fresh conversation answers well (sample 1)
            verdict_json(GROUNDED_CLOSING),  # sample 2 of the vote
        ]
    )

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    assert result.passed
    roles = [m["role"] for m in client.calls[2]["messages"]]
    assert roles == ["system", "user"]  # nothing of the broken round carried over
    spent = {m.metric_id: m.value for m in result.metrics}["llm_closing_integrates"]
    assert spent["clean_retries"] == 1


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


def test_a_quote_that_runs_into_a_list_still_grounds(fake_llm):
    """v12, and the most frequent false rejection left: a lesson introduces its list with a
    lead-in and the model quotes straight through it, dropping the bullet the source puts in
    between. Refusing that is a statement about our formatting, not about the course — the
    same argument emphasis won in v5. `outcomes_extraction` spent 7 retries in 13 calls on
    this alone."""
    data = judged_profile()
    data.entries["lesson_bodies"].value[3]["body"] = (
        "# Wrap up\n\nYou now master four skills:\n\n"
        "- **Navigation:** moving between folders.\n"
        "- **Inspection:** reading files.\n"
    )
    fake_llm(
        closing_integrates=[
            verdict_json("You now master four skills: Navigation: moving between folders.")
        ]
        * 2
    )

    result = run_judged("cr-closing-lesson-integrates", data)

    assert result.passed
    # Stored as the course writes it: the bullet and the emphasis are inside the span.
    assert result.quote == (
        "You now master four skills:\n\n- **Navigation:** moving between folders."
    )
    assert result.quote in data.entries["lesson_bodies"].value[3]["body"]


def test_a_quote_that_carries_the_marker_across_grounds_too(fake_llm):
    """The field run that caught the first attempt at this: dropping the marker only where
    the SOURCE has it — at the start of a line — turned the false negative around instead of
    removing it. A model that copied the ordinal faithfully was then the one refused, and
    `closing_integrates` spent 9 retries in 5 runs on it. Both readings are faithful, so the
    marker is invisible on both sides."""
    data = judged_profile()
    data.entries["lesson_bodies"].value[3]["body"] = (
        "# Wrap up\n\nThe secret is the loop:\n1. **Orient**: run pwd.\n2. **Look**: run ls.\n"
    )
    fake_llm(closing_integrates=[verdict_json("The secret is the loop: 1. Orient: run pwd.")] * 2)

    result = run_judged("cr-closing-lesson-integrates", data)

    assert result.passed
    assert result.quote == "The secret is the loop:\n1. **Orient**: run pwd."


def test_an_outcome_quoted_across_a_bullet_grounds(fake_llm):
    """The oldest retry source in the package: this validator compared bytes against the body
    while every other citation went through `locate`, so a statement quoted across a numbered
    list was refused for the `1. ` the lesson puts there. What is stored is the lesson's own
    span, list markers included."""
    data = outcomes_profile()
    data.entries["lesson_bodies"].value[0]["body"] = (
        "# Welcome\n\nYou will master two skills:\n\n"
        "1. **Navigation**: moving between folders.\n"
        "2. **Inspection**: reading files.\n"
    )
    client = fake_llm(
        outcomes=[
            outcomes_json(
                ("You will master two skills: Navigation: moving between folders.", "move", True)
            )
        ]
    )

    outcomes, _ = tasks.outcomes_extraction(data)

    assert len(client.calls) == 1  # grounded on the first answer: no retry
    assert outcomes[0].statement == (
        "You will master two skills:\n\n1. **Navigation**: moving between folders."
    )


def test_an_index_the_model_quoted_is_still_an_index(fake_llm):
    """Two of five field runs met an upstream that serializes its integers as strings, and
    one died on it — three attempts spent fixing the type, the last of them dropping an entry
    of the twenty. How the answer is encoded is not what it says, the same tolerance
    `_parse_json` already grants a markdown fence."""
    quoted = json.dumps(
        {
            "tasks": [
                {"index": str(index), "reason": "what it asks", "referencesLessonIds": ["00.0"]}
                for index in range(3)
            ]
        }
    )
    client = fake_llm(assessment_reach=[quoted])

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert len(client.calls) == 1  # accepted as it came, no feedback round
    assert not result.passed  # one earlier lesson is not two — the verdict is unaffected


def test_a_hyphen_that_opens_no_list_is_still_text(fake_llm):
    """The rule is narrow on purpose: a marker is a bullet or an ordinal at the start of a
    line AND followed by a space. `-3 degrees` opens nothing, and neither does `1.5`."""
    from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.judgments import locate

    assert locate("it fell to\n-3 degrees today", "-3 degrees") == "-3 degrees"
    assert locate("it took\n1.5 seconds", "1.5 seconds") == "1.5 seconds"
    assert locate("a well-formed id", "well-formed id") == "well-formed id"


def test_an_answer_cut_off_at_the_budget_is_never_fed_back_and_re_rolls_once(fake_llm):
    """Feedback cannot correct a limit — three such attempts once cost nine minutes and
    bought nothing. What a limit CAN get since v8 is one clean conversation (the router
    draws a provider per request); when that one is cut the same way, it raises."""

    client = fake_llm(closing_integrates=['{"reason": "cut off here'] * 3)
    answer = client.complete
    client.complete = lambda **kwargs: dataclasses.replace(  # type: ignore[method-assign]
        answer(**kwargs), finish_reason="length"
    )

    with pytest.raises(AssessorExecutionError, match="without finishing the answer") as e:
        run_judged("cr-closing-lesson-integrates", judged_profile())

    assert e.value.kind == "budget"
    # One call per conversation (a limit is never fed back), two conversations in all.
    assert len(client.calls) == 2


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
            reach_json((0, ["00.0", "00.0", "01.0"]), (1, ["01.0"]), (2, ["01.0"])),
            reach_json((0, ["00.0", "01.0"]), (1, ["01.1"]), (2, ["01.0"])),
        ],
    )
    client = runtime.get_client()

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", data)

    assert result.passed
    feedback = client.calls[1]["messages"][-1]["content"]
    assert "more than once" in feedback


def test_the_extraction_tasks_are_bounded_too(fake_llm):
    client = fake_llm(
        assessment_reach=[reach_json((0, ["00.0", "01.0"]), (1, ["01.1"]), (2, ["01.0"]))],
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
    spec = _SHIPPED_CRITERIA["cr-closing-lesson-projects-forward"]

    result = run_judged("cr-closing-lesson-projects-forward", judged_profile())

    assert not result.passed
    assert result.failure_mode == spec.failure_modes[1]


def test_the_vote_reports_what_the_whole_judgement_spent(fake_llm):
    fake_llm(closing_integrates=[verdict_json(GROUNDED_CLOSING)] * 2)

    result = run_judged("cr-closing-lesson-integrates", judged_profile())

    spent = {m.metric_id: m.value for m in result.metrics}["llm_closing_integrates"]
    assert spent["calls"] == 2  # summed across the samples, not one of them
    assert spent["tokens_in"] == 200
    assert spent["clean_retries"] == 0  # a first-answer verdict says so


# --- v6: the three-way retry, one remedy per failure shape (ADR-0037 §7) ----------------


class ScriptedClient:
    """Feeds `request_structured_output` directly: each step is a completion to return or
    an exception to raise, in order. The queue running dry IS the assertion that nothing
    retried past the script."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls: list[dict] = []

    def complete(self, *, model, messages, temperature, max_tokens, **_):
        self.calls.append({"messages": list(messages)})
        assert self.script, "the scripted transport was asked more than the test allows"
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def completion(text: str, finish_reason: str | None = None) -> LlmCompletion:
    return LlmCompletion(
        text=text, model="m", tokens_in=10, tokens_out=5, latency_ms=1, finish_reason=finish_reason
    )


def ask(client: ScriptedClient):
    return request_structured_output(
        client,
        task_id="probe",
        model="m",
        system_prompt="system",
        user_prompt="user",
        validate=lambda payload: [] if payload == {"ok": True} else ["the payload is not ok"],
        temperature=0.0,
        max_tokens=100,
        reasoning={"effort": "none"},
    )


@pytest.mark.parametrize(
    ("exception", "kind"),
    [
        (LlmConfigurationError("no key"), "configuration"),
        (LlmTransportError("retry budget spent"), "transport"),
        (LlmResponseError("hard 4xx"), "response"),
    ],
)
def test_the_platform_taxonomy_survives_in_the_kind_and_is_never_clean_retried(exception, kind):
    client = ScriptedClient(exception)

    with pytest.raises(AssessorExecutionError) as e:
        ask(client)

    assert e.value.kind == kind
    assert e.value.task == "probe"
    assert len(client.calls) == 1  # the script would have failed a retry loudly


def test_an_answer_cut_at_the_budget_buys_one_clean_conversation():
    """v8: a length-cut runaway is deterministic per provider, and the router draws a
    provider per request — one fresh conversation is one re-roll of that draw."""
    client = ScriptedClient(
        completion('{"ok": fal', finish_reason="length"),
        completion('{"ok": true}'),
    )

    payload, usage = ask(client)

    assert payload == {"ok": True}
    assert usage.clean_retries == 1
    assert [m["role"] for m in client.calls[1]["messages"]] == ["system", "user"]


def test_a_second_budget_cut_raises_and_a_usable_capped_answer_never_spends_the_retry():
    client = ScriptedClient(
        completion('{"ok": fal', finish_reason="length"),
        completion('{"ok": fal', finish_reason="length"),
    )
    with pytest.raises(AssessorExecutionError, match="token budget") as e:
        ask(client)
    assert e.value.kind == "budget"
    assert len(client.calls) == 2

    # An answer that hits the limit and still validates is returned on the spot: a usable
    # answer is a usable answer, and the retry stays unspent.
    client = ScriptedClient(completion('{"ok": true}', finish_reason="length"))
    payload, usage = ask(client)
    assert payload == {"ok": True}
    assert usage.clean_retries == 0


def test_a_contract_never_satisfied_is_kind_contract_and_spends_only_its_conversation():
    """Three DIFFERENT violating answers exhaust the schema budget: that is a model that
    keeps missing, not one that froze — feedback was the right remedy and it lost."""
    client = ScriptedClient(
        completion('{"ok": false}'),
        completion('{"ok": 0}'),
        completion('{"ok": null}'),
    )

    with pytest.raises(AssessorExecutionError, match="never satisfied") as e:
        ask(client)

    assert e.value.kind == "contract"
    assert len(client.calls) == 3


def test_degeneration_is_dissolved_by_a_clean_conversation_at_the_unit_level():
    client = ScriptedClient(
        completion('{"ok": false}'),  # violation, fed back
        completion('{"ok": false}'),  # identical -> degeneration
        completion('{"ok": true}'),  # fresh conversation
    )

    payload, usage = ask(client)

    assert payload == {"ok": True}
    assert usage.clean_retries == 1
    assert usage.calls == 3  # the failed round's spend is not forgotten
    assert [m["role"] for m in client.calls[2]["messages"]] == ["system", "user"]


def test_a_failed_task_is_memoized_so_sibling_criteria_degrade_together(fake_llm):
    """The assessment mapping feeds two criteria (ADR-0037 §2): when it degenerates to
    exhaustion, both see the SAME failure and the model is not re-asked a question that
    just degenerated."""
    client = fake_llm(assessment_mapping=["not json"] * 4)
    data = judged_profile()

    with pytest.raises(AssessorExecutionError) as first:
        run_judged("cr-every-objective-has-an-assessment-item", data)
    calls_after_first = len(client.calls)

    with pytest.raises(AssessorExecutionError) as second:
        run_judged("cr-assessment-matches-the-declared-verification", data)

    assert second.value is first.value  # one failure, one cause, shared
    assert len(client.calls) == calls_after_first  # not one more call


# --- the assessment pair: one mapping, one judgement, two criteria ----------------------


def test_every_objective_has_an_item_is_decided_in_code(fake_llm):
    """The model supplies the mapping; "every objective has at least one" is arithmetic."""
    fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [1]),
                ("obj-2", [0]),
            )
        ]
    )

    result = run_judged("cr-every-objective-has-an-assessment-item", judged_profile())

    assert result.passed


def test_an_objective_measured_only_by_a_proposal_is_measured(fake_llm):
    """The campaign's whole point (ADR-0046): obj-2 is covered by an exercise the draft
    proposes and by nothing it delivers, which used to read as an objective measured by
    nothing at all. The pass is real — and the metric says how much of the coverage rests on
    proposals, because they are written by the same pipeline as the objectives and agreement
    between the two is weaker evidence than a delivered task would be."""
    fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [1]),
                ("obj-2", [2]),
            )
        ]
    )

    result = run_judged("cr-every-objective-has-an-assessment-item", judged_profile())

    assert result.passed
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["objectives_measured_by_proposal_only"] == ["obj-2"]
    assert metrics["assessment_offered"] == {"delivered": 2, "proposed": 1}


def test_the_mapping_is_shown_which_tasks_are_only_proposed(fake_llm):
    """One index space over both kinds, each entry marked and each prompt verbatim: the model
    answers with indices we assigned, and a proposal's several lines cannot read as several
    tasks."""
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [1]),
                ("obj-2", [2]),
            )
        ]
    )

    run_judged("cr-every-objective-has-an-assessment-item", judged_profile())

    corpus = "\n".join(message["content"] for message in client.calls[0]["messages"])
    assert "[1] delivered item (multipleChoice): Build a page from this brief." in corpus
    assert "[2] proposed exercise (codeChallenge): In this exercise" in corpus
    assert PROPOSED_EXERCISE in corpus  # verbatim, its line break included


def test_an_unmeasured_objective_fails_and_is_named(fake_llm):
    fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [1]),
                ("obj-2", []),
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
    data.entries["assessment_offerings"].value[0]["prompt"] = question
    client = fake_llm(assessment_mapping=[mapping_json(("obj-1", [0]), ("obj-2", []))])

    result = run_judged("cr-every-objective-has-an-assessment-item", data)

    assert len(client.calls) == 1  # grounded on the first answer: no retry, no abort
    corpus = "\n".join(m["content"] for m in client.calls[0]["messages"])
    assert question in corpus  # shown unescaped, exactly as the course writes it
    assert not result.passed  # obj-2 has no item, which is this criterion's finding


def test_the_two_assessment_criteria_share_one_mapping(fake_llm):
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [1]),
                ("obj-2", [0]),
            )
        ],
        assessment_verification_match=[verification_json(("obj-1", [1], True))] * 2,
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
    and there is nothing to compare for an objective no task bears on."""
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [1]),
                ("obj-2", [0]),
            )
        ],
        assessment_verification_match=[verification_json(("obj-1", [1], True))] * 2,
    )

    run_judged("cr-assessment-matches-the-declared-verification", judged_profile())

    asked = "\n".join(m["content"] for m in client.calls[1]["messages"])
    assert "obj-1" in asked and "Builds one" in asked
    assert "obj-2" not in asked  # declares no verification


def test_the_verification_judge_sees_whether_a_task_is_delivered_or_proposed(fake_llm):
    """The criterion's pass condition says a proposed exercise counts as what the draft
    offers to verify an objective. The judge can only apply that sentence knowingly if the
    corpus says which is which — otherwise it would be weighing a declared verification
    against a task it cannot tell has been built."""
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [2]),
                ("obj-2", [0]),
            )
        ],
        assessment_verification_match=[verification_json(("obj-1", [2], True))] * 2,
    )

    result = run_judged("cr-assessment-matches-the-declared-verification", judged_profile())

    assert result.passed
    asked = "\n".join(message["content"] for message in client.calls[1]["messages"])
    assert "proposed exercise (codeChallenge)" in asked
    assert "Builds one" in asked  # obj-1's declared verification, beside what measures it


def test_each_task_is_numbered_by_its_own_index_in_the_offerings(fake_llm):
    """One number means one task everywhere in this package: the judge cites in the same
    index space the mapping answers in, so a citation resolves to a row of the profile."""
    client = fake_llm(
        assessment_mapping=[mapping_json(("obj-1", [1, 2]), ("obj-2", []))],
        assessment_verification_match=[verification_json(("obj-1", [1], True))] * 2,
    )

    run_judged("cr-assessment-matches-the-declared-verification", judged_profile())

    asked = "\n".join(message["content"] for message in client.calls[1]["messages"])
    assert "[1] delivered item (multipleChoice): Build a page from this brief." in asked
    assert "[2] proposed exercise (codeChallenge): In this exercise" in asked
    assert "never copy their text" in asked


def test_one_unsatisfied_objective_fails_the_criterion(fake_llm):
    """The aggregation is code's. Asked for one verdict over every objective at once, the
    judge did it itself and contradicted its own reason — a sample that wrote "satisfied
    except obj-3" answered true. Now each objective answers for itself and the criterion is
    the conjunction."""
    data = judged_profile()
    data.entries["declared_objectives"].value[1]["verifiableBy"] = "Styles one"
    fake_llm(
        assessment_mapping=[mapping_json(("obj-1", [1]), ("obj-2", [0]))],
        assessment_verification_match=[
            verification_json(("obj-1", [1], True), ("obj-2", [0], False, 1))
        ]
        * 2,
    )

    result = run_judged("cr-assessment-matches-the-declared-verification", data)

    assert not result.passed
    # the failing objective's mode, not the first declared one
    assert result.failure_mode == _SHIPPED_CRITERIA[VERIFICATION].failure_modes[1]
    # and the quote is the task it cited, fetched from the profile
    assert result.quote == "Which tag opens a document?"
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert [entry["objectiveId"] for entry in metrics["verification_by_objective"]] == [
        "obj-1",
        "obj-2",
    ]
    assert metrics["verification_failed_by_sample"] == [["obj-2"], ["obj-2"]]


def test_two_samples_that_fail_different_objectives_are_both_reported(fake_llm):
    """Where the next instrument decision comes from: samples agreeing on the verdict and
    naming different objectives disagree about the facts, while samples naming the same one
    and splitting disagree about the bar. The verdict alone cannot tell them apart."""
    data = judged_profile()
    data.entries["declared_objectives"].value[1]["verifiableBy"] = "Styles one"
    fake_llm(
        assessment_mapping=[mapping_json(("obj-1", [1]), ("obj-2", [0]))],
        assessment_verification_match=[
            verification_json(("obj-1", [1], False, 0), ("obj-2", [0], True)),
            verification_json(("obj-1", [1], True), ("obj-2", [0], False, 1)),
        ],
    )

    result = run_judged("cr-assessment-matches-the-declared-verification", data)

    assert not result.passed  # both samples fail the criterion, for different reasons
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["verification_failed_by_sample"] == [["obj-1"], ["obj-2"]]
    assert metrics["judgment_agreement_assessment_verification_match"] == {
        "samples": 2,
        "agreed": 2,
    }


def test_citing_a_task_that_belongs_to_another_objective_is_refused(fake_llm):
    """The closed-set form of the grounding rule: the judge may only cite the tasks its own
    block listed, so a number borrowed from a neighbour is a contract violation rather than
    an interpretation."""
    data = judged_profile()
    data.entries["declared_objectives"].value[1]["verifiableBy"] = "Styles one"
    client = fake_llm(
        assessment_mapping=[mapping_json(("obj-1", [1]), ("obj-2", [0]))],
        assessment_verification_match=[
            verification_json(("obj-1", [0], True), ("obj-2", [0], True)),
            *[verification_json(("obj-1", [1], True), ("obj-2", [0], True))] * 2,
        ],
    )

    result = run_judged("cr-assessment-matches-the-declared-verification", data)

    assert result.passed
    assert "not a task listed under this objective" in _feedback_of(client)


def test_an_objective_decided_on_nothing_is_refused(fake_llm):
    """A verdict with no citation behind it is not evidence (ADR-0009), and with numbers
    instead of quotes the rule costs one line."""
    client = fake_llm(
        assessment_mapping=[mapping_json(("obj-1", [1]), ("obj-2", []))],
        assessment_verification_match=[
            verification_json(("obj-1", [], True)),
            *[verification_json(("obj-1", [1], True))] * 2,
        ],
    )

    run_judged("cr-assessment-matches-the-declared-verification", judged_profile())

    assert "non-empty array of task numbers" in _feedback_of(client)


def test_verification_match_is_vacuous_when_nothing_declares_one(fake_llm):
    data = judged_profile()
    data.entries["declared_objectives"].value[0]["verifiableBy"] = None
    client = fake_llm(
        assessment_mapping=[
            mapping_json(
                ("obj-1", [1]),
                ("obj-2", [0]),
            )
        ]
    )

    result = run_judged("cr-assessment-matches-the-declared-verification", data)

    assert result.passed
    assert len(client.calls) == 1  # nothing worth asking a judge
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["verification_pairs_judged"] == 0


# --- assessment reach: extraction, then a count -----------------------------------------


def test_assessment_reach_counts_earlier_lessons_outside_the_task_s_module(fake_llm):
    fake_llm(
        assessment_reach=[reach_json((0, ["00.0", "01.0"]), (1, ["01.1", "02.0"]), (2, ["01.1"]))]
    )

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert result.passed  # 00.0, 01.0 and 01.1 are earlier and outside module 02
    metrics = {m.metric_id: m.value for m in result.metrics}
    assert metrics["assessment_reaches_back_to"] == ["00.0", "01.0", "01.1"]


def test_a_proposed_exercise_reaches_back_like_a_delivered_one(fake_llm):
    """ADR-0046: what the learner must have studied to do a task does not depend on who
    materializes it. The same answers that fail one lesson short in the test above pass here
    because the proposal draws on a module the delivered tasks never touch — which is the
    shape of a draft that ships one quiz block and proposes everything else."""
    fake_llm(assessment_reach=[reach_json((0, ["01.0"]), (1, ["02.0"]), (2, ["00.0", "01.0"]))])

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert result.passed
    metrics = {m.metric_id: m.value for m in result.metrics}
    # 01.0 from the delivered task in 02.0, 00.0 from the proposal in 01.1; the proposal's
    # own module (01) does not count for it, which is the same rule the items obey.
    assert metrics["assessment_reaches_back_to"] == ["00.0", "01.0"]


def test_assessment_that_only_tests_its_own_module_fails(fake_llm):
    fake_llm(assessment_reach=[reach_json((0, ["02.0"]), (1, ["02.0"]), (2, ["01.1"]))])

    result = run_judged("cr-assessment-retrieves-earlier-taught-material", judged_profile())

    assert not result.passed
    assert (
        result.failure_mode
        == _SHIPPED_CRITERIA["cr-assessment-retrieves-earlier-taught-material"].failure_modes[0]
    )


def test_one_earlier_lesson_is_not_enough(fake_llm):
    fake_llm(assessment_reach=[reach_json((0, ["01.0"]), (1, ["02.0"]), (2, ["01.1"]))])

    assert not run_judged(
        "cr-assessment-retrieves-earlier-taught-material", judged_profile()
    ).passed


def test_a_reach_answer_naming_a_lesson_the_plan_never_declared_is_refused(fake_llm):
    """The closed-set form of the grounding rule: an invented lesson would be counted."""
    client = fake_llm(
        assessment_reach=[
            reach_json((0, ["99.9"]), (1, ["02.0"]), (2, ["01.0"])),
            reach_json((0, ["00.0", "01.0"]), (1, ["01.1"]), (2, ["01.0"])),
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
    assert "not a quote from the lesson" in client.calls[1]["messages"][-1]["content"]
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


def fixture_prose(data: ProfileData, lesson_id: str) -> str:
    """A plain prose line of one fixture lesson — what a well-behaved model would quote, and
    what `grounding.locate` has to find in the body the task showed."""
    shown = next(one for one in tasks.all_lessons(data) if one["lessonId"] == lesson_id)
    return next(
        line.strip()
        for line in str(shown["body"]).splitlines()
        if len(line.strip()) > 40 and not line.strip().startswith(("#", "-", "*", ">", "|", "`"))
    )


def _instrument_spec() -> InstrumentSpec:
    return InstrumentSpec(
        instrument_version_id="course-drafts-qa-v10",
        instrument_id=_SHIPPED_SPEC["instrument_id"],
        status="published",
        claims=tuple(ClaimSpec(claim_id=raw["id"]) for raw in _SHIPPED_SPEC["claims"]),
        criteria=tuple(_SHIPPED_CRITERIA[raw["id"]] for raw in _SHIPPED_SPEC["criteria"]),
        bindings=tuple(
            BindingSpec(
                package_format=raw["package_format"],
                task_variables=raw.get("task_variables", {}),
            )
            for raw in _SHIPPED_SPEC["bindings"]
        ),
    )


def test_the_package_against_the_frozen_v2_fixture(fake_llm):
    """The exact partition over the real draft, with the fake transport answering what a
    well-behaved model would: the four semantic criteria and the seven judged ones EXECUTE
    (they no longer derive `not_assessed`, which is this artifact's reason to exist), the
    structural results match `drafts-structural`'s pinned run, and the memoization holds.

    Pinned to v9 since the old versions were deleted, which changes one outcome:
    `cr-cognitive-demand-rises-across-the-course` used to derive `not_applicable` because v7
    did not require `lesson_concept_coverage`. v8 and v9 do, the fixture carries it, so the
    criterion now EXECUTES and the trajectory task is asked for. The two criteria v9 splits
    out of `cr-later-lessons-apply-earlier-concepts` execute since v13, over one concept map
    the pair shares — six more calls, one per module plus the definitions pass."""
    fixture = _fixture_profile()
    opening_body, _ = tasks.opening_lesson_body(fixture)
    closing_body, _ = judgments.closing_lesson_body(fixture)
    grounded = next(line for line in opening_body.splitlines() if line.strip()).strip()
    grounded_closing = next(line for line in closing_body.splitlines() if line.strip()).strip()
    objective_count = len(fixture.entries["learning_objectives"].value)
    objective_ids = [str(o["id"]) for o in fixture.entries["declared_objectives"].value]
    offerings = list(fixture.entries["assessment_offerings"].value)

    # The trajectory task is asked about the CORE lessons only — the frame ones are excluded
    # because they bound the arc rather than advance it.
    core_ids = [str(lesson["lessonId"]) for lesson in tasks.ordered_inventory(fixture)[1:-1]]

    # The concept map, answered the way the draft actually reads: each module opens a concept
    # and its later lessons work with it, and each module after the first also works with
    # something an earlier module opened. Concepts are named, not indexed by hand.
    concept_index = {name: index for index, name in enumerate(tasks.distinct_concepts(fixture))}
    markup, syntax = "HTML as markup language", "HTML element syntax"
    anchors, whole_page = "Anchor elements", "Complete HTML page construction"
    introduces = {markup: "01.0", syntax: "02.0", anchors: "03.0", whole_page: "04.0"}
    works_with = {
        "00": (),
        "01": (("01.1", markup, "uses_as_known"),),
        "02": (
            ("02.0", markup, "uses_as_known"),
            ("02.1", syntax, "uses_as_known"),
            ("02.2", syntax, "assessed"),
        ),
        "03": (
            ("03.0", syntax, "uses_as_known"),
            ("03.1", anchors, "uses_as_known"),
            ("03.2", anchors, "develops"),
        ),
        "04": (
            ("04.0", anchors, "uses_as_known"),
            ("04.1", whole_page, "uses_as_known"),
        ),
    }
    concept_map_answers = {
        "definitions": concept_map_json(
            *(
                (concept_index[name], "defines", [(lesson_id, fixture_prose(fixture, lesson_id))])
                for name, lesson_id in introduces.items()
            )
        ),
        **{
            module: concept_map_json(
                *(
                    (concept_index[name], group, [(lesson_id, fixture_prose(fixture, lesson_id))])
                    for lesson_id, name, group in works_with[module]
                )
            )
            for module in sorted(works_with)
        },
    }

    client = fake_llm(
        concept_map=concept_map_answers,
        outcomes=[outcomes_json((grounded, "build", True))],
        # v9 requires `lesson_concept_coverage`, which the fixture carries, so the trajectory
        # task is reached now — answered non-decreasing so the criterion passes.
        # Non-decreasing, so the criterion passes: a flat trajectory is what the rule
        # refuses once a course has enough core lessons to show growth.
        trajectory=[
            trajectory_json(
                {lesson_id: min(2 + index, 5) for index, lesson_id in enumerate(core_ids)}
            )
        ],
        objectives=[
            objectives_json(
                *[("understand", True), ("apply", True), ("create", True)][:objective_count]
            )
        ],
        opening_connects_backwards=[verdict_json(grounded)] * 2,
        closing_integrates=[verdict_json(grounded_closing)] * 2,
        closing_projects_forward=[verdict_json(grounded_closing)] * 2,
        arc_character=[verdict_json(grounded_closing)] * 2,
        assessment_mapping=[mapping_json(*((objective_id, [0]) for objective_id in objective_ids))],
        assessment_verification_match=[
            verification_json(*((objective_id, [0], True) for objective_id in objective_ids))
        ]
        * 2,
        # From the fourth task on, answered to draw on two earlier lessons from other
        # modules; the ones before it test only their own.
        assessment_reach=[
            reach_json(
                *(
                    (index, ["00.0", "01.0"] if index >= 3 else [str(offering["lessonId"])])
                    for index, offering in enumerate(offerings)
                )
            )
        ],
    )

    outcomes, metrics = derive_and_execute(
        _instrument_spec(), fixture, PACKAGE.coverage, dict(PACKAGE.executors)
    )

    assert len(outcomes) == 30
    by_outcome: dict[str, set[str]] = {}
    for outcome in outcomes:
        by_outcome.setdefault(outcome.outcome, set()).add(outcome.criterion_id)

    assert by_outcome["not_applicable"] == {"cr-prerequisites-declared"}
    assert by_outcome["pass"] == {
        # the structural six, exactly as drafts-structural's pinned run
        "cr-audience-declared",
        # reached now that v9 requires the concept coverage the fixture carries
        "cr-cognitive-demand-rises-across-the-course",
        "cr-course-has-development",
        "cr-course-opens-with-general-intro",
        "cr-module-structure-well-formed",
        "cr-no-lesson-spikes-in-lexical-load",
        "cr-objectives-min-count",
        # the semantic four, executed at last
        "cr-objectives-observable-verbs",
        "cr-outcomes-present",
        "cr-outcomes-observable-verbs",
        "cr-objectives-non-decreasing-demand",
        # the judged seven, executed at last
        "cr-opening-lesson-connects-backwards",
        "cr-closing-lesson-integrates",
        "cr-closing-lesson-projects-forward",
        "cr-arc-character",
        "cr-every-objective-has-an-assessment-item",
        "cr-assessment-matches-the-declared-verification",
        "cr-assessment-retrieves-earlier-taught-material",
        # the continuity pair, executed since v13 over the map the two of them share
        "cr-lessons-build-within-their-module",
        "cr-modules-build-on-earlier-modules",
    }
    # The abstains restricted to what THIS instrument version declares. Since v9 the artifact
    # decides ids v2 never had, and an outcome is only derived for a criterion the pinned
    # version carries.
    declared_here = {outcome.criterion_id for outcome in outcomes}
    assert by_outcome["not_assessed"] == set(PACKAGE.coverage.abstains) & declared_here
    assert "fail" not in by_outcome and "no_evidence" not in by_outcome
    assert all(not o.derived and o.quote for o in outcomes if o.outcome == "pass")

    # Fourteen criteria, twenty-one calls: five judged criteria are voted on twice each, two
    # share the outcomes extraction and two share the assessment mapping, the trajectory task
    # is asked once, and the concept map costs six — the definitions pass over the whole
    # course plus one usage call per module — which the continuity pair shares.
    assert len(client.calls) == 21
    assert sum(1 for call in client.calls if call["task_id"] == "concept_map") == 6

    metric_values = {m.metric_id: m.value for m in metrics}
    assert metric_values["stated_outcomes_count"] == 1
    assert len(metric_values["objective_bloom_levels"]) == objective_count
    # Present since this test moved to v9: the trajectory criterion executes now, and its
    # metric is the classification the executor decided on.
    assert len(metric_values["concept_sophistication_levels"]) == len(core_ids)
    assert metric_values["objectives_unmeasured"] == []
    assert metric_values["assessment_reaches_back_to"] == ["00.0", "01.0"]
    # The continuity pair, and the map they read: every interior lesson works with what its
    # module opened, and every module after the first works with an earlier module's concept.
    assert metric_values["module_internal_build"] == {"of": 6, "built": 6}
    assert metric_values["cross_module_build"] == {"of": 3, "built": 3}
    assert metric_values["concept_map_coverage"]["dropped"] == 0
    assert metric_values["llm_concept_map"]["calls"] == 6
    for task_id in ("outcomes_extraction", "objectives_classification"):
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
    spec = copy.deepcopy(_SHIPPED_SPEC)
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
