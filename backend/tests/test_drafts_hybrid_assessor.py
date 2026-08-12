"""`drafts-hybrid` v2 — the semantic executors over a fake transport, the coverage vs the
real v3 YAML, the whole package against the frozen LearnpackV2 fixture, and ratification.

The fake replaces the TRANSPORT only (the seam is `runtime.get_client`, ADR-0034):
everything semantic — prompts, validation, grounding, feedback retries, the decision
constants — runs for real. The structural seven are copies whose arithmetic is already
pinned by the structural test files; here they appear through the whole-package run.

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
from app.modules.evaluation.infrastructure.assessors import AUTOMATED_ASSESSORS
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import runtime, tasks
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError
from app.modules.identity.infrastructure.repository import SqlAlchemyAssessorRepository
from app.platform.db import SessionLocal
from app.platform.llm import LlmCompletion, LlmTransportError
from tests.conftest import INSTRUMENTS_DIR

PACKAGE = AUTOMATED_ASSESSORS[("drafts-hybrid", "2")]

_V3_SPEC = yaml.safe_load(
    (INSTRUMENTS_DIR / "course-drafts-qa-v3.yaml").read_text(encoding="utf-8")
)
_V3_CRITERIA = {
    raw["id"]: CriterionSpec(
        criterion_id=raw["id"],
        pass_condition=raw["pass_condition"],
        failure_modes=tuple(raw["failure_modes"]),
        claim_ids=tuple(raw["claims"]),
        required_data=tuple(raw["requires"]),
        on_missing_evidence=raw.get("on_missing_evidence", "no_evidence"),
        condition=raw.get("condition"),
    )
    for raw in _V3_SPEC["criteria"]
}


# --- the fake transport (the ADR-0034 seam) --------------------------------------------


class FakeLlmClient:
    """Routes each call to a canned-answer queue by the task tag in the user prompt.

    Queues hold raw response TEXTS so a test can feed one bad answer and then a good one —
    the feedback-retry loop runs for real against them."""

    def __init__(
        self,
        outcomes: list[str] | None = None,
        objectives: list[str] | None = None,
        trajectory: list[str] | None = None,
    ) -> None:
        self._queues = {
            "<lesson>": list(outcomes or []),
            "<objectives>": list(objectives or []),
            "<plan>": list(trajectory or []),
        }
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
        prompt_text = "\n".join(m["content"] for m in messages)
        for tag, queue in self._queues.items():
            if tag in prompt_text:
                assert queue, f"fake transport has no answer left for {tag}"
                return LlmCompletion(
                    text=queue.pop(0), model=model, tokens_in=100, tokens_out=40, latency_ms=7
                )
        raise AssertionError("no task tag found in the prompt")


@pytest.fixture(autouse=True)
def isolated_task_cache():
    tasks.clear_task_cache()
    yield
    tasks.clear_task_cache()


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


def test_coverage_is_a_disjoint_union_over_v3():
    declared = {raw["id"] for raw in _V3_SPEC["criteria"]}
    assert PACKAGE.coverage.declared == declared
    assert not (PACKAGE.coverage.executes & set(PACKAGE.coverage.abstains))
    assert PACKAGE.instrument_id == _V3_SPEC["instrument_id"]
    assert len(PACKAGE.coverage.executes) == 12


def test_coverage_also_decides_every_criterion_of_v1_and_v2():
    """Criterion ids are stable across the lineage (v3 changed one criterion's `requires`,
    no ids), so the one artifact can ratify any published version (ADR-0019)."""
    for version in ("v1", "v2"):
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
        assert len(_V3_CRITERIA[criterion_id].failure_modes) >= needed


def test_source_config_declares_the_semantic_identity():
    """ADR-0034: models and prompts travel in SOURCE_CONFIG, so the ratification guard
    refuses any of them drifting without a VERSION bump."""
    llm = PACKAGE.source_config["llm"]
    assert set(llm["models"]) == {
        "outcomes_extraction",
        "objectives_classification",
        "concept_trajectory",
    }
    assert llm["temperature"] == 0.0
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
    spec = _V3_CRITERIA["cr-objectives-observable-verbs"]
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
    spec = _V3_CRITERIA["cr-objectives-non-decreasing-demand"]
    run = PACKAGE.executors["cr-objectives-non-decreasing-demand"]
    data = profile(learning_objectives=["analyze systems", "recall terms", "apply patterns"])

    # analyze (4) -> remember (1): a fall of 3, far past the one-level consolidation dip.
    fake_llm(objectives=[objectives_json(("analyze", True), ("remember", True), ("apply", True))])
    verdict = run(spec, data)

    assert not verdict.passed
    assert verdict.failure_mode == spec.failure_modes[0]
    assert verdict.quote == "recall terms"  # the objective where the sequence fell back


def test_objectives_non_decreasing_demand_flat_and_short_sequences(fake_llm):
    spec = _V3_CRITERIA["cr-objectives-non-decreasing-demand"]
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
    spec = _V3_CRITERIA["cr-outcomes-present"]
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
    spec = _V3_CRITERIA["cr-outcomes-observable-verbs"]
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
    spec = _V3_CRITERIA["cr-cognitive-demand-rises-across-the-course"]
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
    spec = _V3_CRITERIA["cr-cognitive-demand-rises-across-the-course"]
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

    present = PACKAGE.executors["cr-outcomes-present"](_V3_CRITERIA["cr-outcomes-present"], data)
    verbs = PACKAGE.executors["cr-outcomes-observable-verbs"](
        _V3_CRITERIA["cr-outcomes-observable-verbs"], data
    )

    assert present.passed and verbs.passed
    assert len(client.calls) == 1  # the second criterion read the memoized extraction


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
        instrument_version_id="course-drafts-qa-v3",
        instrument_id=_V3_SPEC["instrument_id"],
        status="published",
        claims=tuple(ClaimSpec(claim_id=raw["id"]) for raw in _V3_SPEC["claims"]),
        criteria=tuple(_V3_CRITERIA[raw["id"]] for raw in _V3_SPEC["criteria"]),
        bindings=tuple(
            BindingSpec(
                package_format=raw["package_format"],
                task_variables=raw.get("task_variables", {}),
            )
            for raw in _V3_SPEC["bindings"]
        ),
    )


def test_the_package_against_the_frozen_v2_fixture(fake_llm):
    """The exact partition over the real draft, with the fake transport answering what a
    well-behaved model would: the five semantic criteria EXECUTE (they no longer derive
    `not_assessed`, which is this artifact's reason to exist), the structural results
    match `drafts-structural`'s pinned run, and three LLM calls cover five criteria."""
    fixture = _fixture_profile()
    opening_body, _ = tasks.opening_lesson_body(fixture)
    grounded = next(line for line in opening_body.splitlines() if line.strip()).strip()
    objective_count = len(fixture.entries["learning_objectives"].value)
    core_ids = [
        str(lesson["lessonId"])
        for lesson in sorted(
            fixture.entries["lesson_inventory"].value, key=lambda entry: entry["position"]
        )
    ][1:-1]
    rising = [1 + (n * 4) // max(len(core_ids) - 1, 1) for n in range(len(core_ids))]

    client = fake_llm(
        outcomes=[outcomes_json((grounded, "build", True))],
        objectives=[
            objectives_json(
                *[("understand", True), ("apply", True), ("create", True)][:objective_count]
            )
        ],
        trajectory=[trajectory_json(dict(zip(core_ids, rising, strict=True)))],
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
    }
    assert by_outcome["not_assessed"] == set(PACKAGE.coverage.abstains)
    assert "fail" not in by_outcome and "no_evidence" not in by_outcome
    assert all(not o.derived and o.quote for o in outcomes if o.outcome == "pass")

    assert len(client.calls) == 3  # five criteria, three questions — memoization held

    metric_values = {m.metric_id: m.value for m in metrics}
    assert metric_values["stated_outcomes_count"] == 1
    assert len(metric_values["objective_bloom_levels"]) == objective_count
    assert metric_values["concept_sophistication_levels"] == rising
    for task_id in ("outcomes_extraction", "objectives_classification", "concept_trajectory"):
        spent = metric_values[f"llm_{task_id}"]
        assert spent["calls"] == 1 and spent["tokens_in"] > 0


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
    spec = copy.deepcopy(_V3_SPEC)
    spec["instrument_id"] = f"qa-hybrid-{unique}"
    return spec


def test_ratifying_v3_stores_the_semantic_identity(
    cleanup, unique, namespace, admin, patched_hybrid_package
):
    """The registration act persists SOURCE_CONFIG whole — models, temperature and the
    prompts fingerprint included — which is what arms the drift guard for every later
    ratification (ADR-0034 clause 1)."""
    admin_id, email = admin

    v3_id = publish_instrument(cleanup, hybrid_copy_spec(unique), admin_id)
    ratified = run_ratify_assessor(
        patched_hybrid_package.name, patched_hybrid_package.version, v3_id, email, []
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
