"""Executors of the `drafts-hybrid` assessor — every verdict is decided by code.

Two kinds under one signature. The structural seven are a COPY of `drafts-structural`
v1's executors, not an import: sharing the functions would tie two assessors' identities
together (ADR-0016 gives an algorithm its identity through the assessor's version, and a
change to a shared module would silently change both artifacts). The five semantic ones
call this package's tasks — extraction and classification by an LLM — and then decide
pass/fail deterministically over what came back: a count, an order check, a trajectory
rule. The model supplies data, never verdicts; the decision constants below are as much
this assessor's identity as any prompt (ADR-0034).

Editing this file is a new version of `drafts-hybrid` and says nothing about
`drafts-structural` or `structural`.

Each executor realizes one criterion's pass condition (ADR-0016: the mapping
criterion -> executor is this assessor's internal detail, never the instrument's).
Profiles arrive with their value domains verified (ADR-0020), so shapes are assumed.
Evidence discipline: every result quotes verbatim profile data — the entry's canonical
quote, or a substring of it (an objective's text, an extracted statement the grounding
check verified against the body) — ADR-0009.

Failure modes are chosen BY POSITION from the criterion's declared list — the wording
lives in the instrument only. Reordering an instrument's failure modes is a normative
change this selection follows blindly; the human layer 2 (ADR-0015) verifies
norm/realization consistency, and any undeclared mode is rejected at derivation time.

Module mechanics mirror the lesson-id convention the instrument's data requirements
describe: lesson ids parse as 'NN.M', module = the 'NN' prefix, module 00 is the
course-level introduction slot and the last lesson (by declared position) is the closing
slot.
"""

import json
import re
import statistics
from itertools import pairwise
from typing import Any

from app.modules.evaluation.domain.model import (
    ComputedMetric,
    CriterionSpec,
    ExecutorResult,
    ProfileData,
    ProfileEntryData,
)
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import measures, tasks
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.structured_output import (
    LlmUsage,
)

_LESSON_ID = re.compile(r"^(\d{2})\.(\d+)$")
_AUDIENCE_BOILERPLATE = frozenset({"everyone", "anyone", "anyone interested"})

# How far above its own course's median a lesson's lexical load may sit. Empirical, set
# against the frozen corpus, and larger than the disagreement between reasonable
# implementations of the measure — otherwise the verdict would be decided by the
# implementation rather than by the text. The evidence is in docs/MEASUREMENT.md; do not
# move it without redoing that work.
LEXICAL_LOAD_SPIKE = 0.20

# --- the semantic decision constants (identity, ADR-0034) -------------------------------
# A successive objective may sit one Bloom level below its predecessor (consolidation);
# two or more is the sequence falling back — the pass condition's own words.
ALLOWED_BLOOM_DROP = 1
# "Flat across a course long enough to progress": with 3 objectives one level can be a
# legitimate scope decision; from this many on, a flat sequence is a course that does not
# build. Pinned by the calibration tests; moving it is a new version.
FLAT_MIN_OBJECTIVES = 4
# A core lesson may consolidate one level below the sophistication the course already
# reached; sitting two or more below the running peak is working below what the course
# already required.
ALLOWED_SOPHISTICATION_DIP = 1
# From this many core lessons on, an all-equal trajectory is a list rather than a
# progression; below it, flatness proves nothing.
FLAT_MIN_CORE_LESSONS = 5

# Fail-quote excerpts: enough opening-lesson text to verify "it states no outcomes"
# without dumping a whole body into the report.
_EXCERPT_CHARS = 300


def _entry(profile: ProfileData, data_requirement_id: str) -> ProfileEntryData:
    return profile.entries[data_requirement_id]


def _result(
    entry: ProfileEntryData,
    passed: bool,
    spec: CriterionSpec,
    failure_index: int | None = None,
    metrics: tuple[ComputedMetric, ...] = (),
    quote: str | None = None,
) -> ExecutorResult:
    return ExecutorResult(
        passed=passed,
        quote=quote if quote is not None else (entry.quote or ""),
        locator=entry.locator,
        failure_mode=None if passed else spec.failure_modes[failure_index or 0],
        metrics=metrics,
    )


def _usage_metric(task_id: str, usage: LlmUsage) -> ComputedMetric:
    """What the task spent, as evidence that travels with the evaluation (ADR-0034)."""
    return ComputedMetric(
        f"llm_{task_id}",
        {
            "model": usage.model,
            "calls": usage.calls,
            "tokens_in": usage.tokens_in,
            "tokens_out": usage.tokens_out,
            "latency_ms": usage.latency_ms,
        },
    )


def _excerpt(text: str) -> str:
    return text.strip()[:_EXCERPT_CHARS]


# --- declaration criteria (structural, copied) ------------------------------------------


def objectives_min_count(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """At least 2 non-blank learning objectives declared."""
    entry = _entry(profile, "learning_objectives")
    declared = [o for o in entry.value if str(o).strip()]
    # Named `declared_objectives_count`, NOT `declared_objectives` (structural v1's name):
    # this lineage mints a data requirement with that exact id — the objectives themselves,
    # each with its declared verification — and a report line `declared_objectives: 5` must
    # not be ambiguous between a count and a list.
    metrics = (ComputedMetric("declared_objectives_count", len(declared)),)
    if len(declared) >= 2:
        return _result(entry, True, spec, metrics=metrics)
    # 0 -> omitted entirely; 1 -> a single catch-all objective.
    return _result(entry, False, spec, 0 if not declared else 1, metrics)


def audience_declared(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """A non-empty, non-boilerplate target audience statement."""
    entry = _entry(profile, "target_audience")
    statement = str(entry.value or "").strip()
    if not statement:
        return _result(entry, False, spec, 0)
    if statement.lower().rstrip(".") in _AUDIENCE_BOILERPLATE:
        return _result(entry, False, spec, 1)
    return _result(entry, True, spec)


def prerequisites_declared(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """At least one prerequisite; an explicit 'none' also counts as a declaration."""
    entry = _entry(profile, "prerequisites")
    declared = [str(p).strip() for p in entry.value if str(p).strip()]
    return _result(entry, bool(declared), spec, 0)


# --- structural criteria over the lesson index (copied) ---------------------------------


def _positions(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lessons in declared order (position when present, list order as fallback)."""

    def declared_order(lesson: dict[str, Any]) -> float:
        position = lesson.get("position")
        return float(position) if position is not None else float("inf")

    return sorted(inventory, key=declared_order)


def _module(lesson_id: str) -> str | None:
    match = _LESSON_ID.match(lesson_id)
    return match.group(1) if match else None


def module_structure_well_formed(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """Every id parses as NN.M; modules contiguous from 00; lessons start at .0."""
    entry = _entry(profile, "lesson_inventory")
    inventory = list(entry.value)

    lesson_ids = [str(lesson["lessonId"]) for lesson in inventory]
    malformed = [lesson_id for lesson_id in lesson_ids if not _LESSON_ID.match(lesson_id)]
    if malformed or len(set(lesson_ids)) != len(lesson_ids):
        return _result(entry, False, spec, 0)

    by_module: dict[int, list[int]] = {}
    for lesson_id in lesson_ids:
        match = _LESSON_ID.match(lesson_id)
        assert match is not None  # guarded above
        by_module.setdefault(int(match.group(1)), []).append(int(match.group(2)))

    modules = sorted(by_module)
    contiguous = modules == list(range(modules[0], modules[0] + len(modules)))
    if not contiguous or modules[0] != 0:
        return _result(entry, False, spec, 1)
    if any(min(numbers) != 0 for numbers in by_module.values()):
        return _result(entry, False, spec, 0)
    metrics = (ComputedMetric("module_count", len(modules)),)
    return _result(entry, True, spec, metrics=metrics)


def course_opens_with_general_intro(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """Module 00 exists and holds exactly one lesson."""
    entry = _entry(profile, "lesson_inventory")
    intro = [lesson for lesson in entry.value if _module(str(lesson["lessonId"])) == "00"]
    return _result(entry, len(intro) == 1, spec, 0)


def course_has_development(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """At least two lessons follow the opening slot."""
    entry = _entry(profile, "lesson_inventory")
    ordered = _positions(list(entry.value))
    has_module_00 = any(_module(str(lesson["lessonId"])) == "00" for lesson in ordered)
    development = (
        [lesson for lesson in ordered if _module(str(lesson["lessonId"])) != "00"]
        if has_module_00
        else ordered[1:]
    )
    metrics = (ComputedMetric("development_lessons", len(development)),)
    return _result(entry, len(development) >= 2, spec, 0, metrics)


# --- the lexical-load measure (copied) --------------------------------------------------


def no_lesson_spikes_in_lexical_load(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """No lesson's vocabulary sits more than LEXICAL_LOAD_SPIKE above the course's median.

    Relative to the course on purpose: the absolute level of the measure tracks subject
    matter (neural networks use longer words than HTML tags) and not pedagogy, so an
    absolute band would mostly report the topic. See docs/MEASUREMENT.md."""
    bodies = _entry(profile, "lesson_bodies")
    by_slug = measures.lexical_load_by_lesson(list(bodies.value))
    if not by_slug:
        # Every lesson too short to carry a stable mean: nothing to compare, nothing broken.
        return _result(bodies, True, spec, metrics=(ComputedMetric("lessons_measured", 0),))

    median = statistics.median(by_slug.values())
    spikes = sorted(slug for slug, load in by_slug.items() if load - median > LEXICAL_LOAD_SPIKE)
    metrics = (
        ComputedMetric("lessons_measured", len(by_slug)),
        ComputedMetric("lexical_load_median", round(median, 4)),
        ComputedMetric("lexical_load_max", round(max(by_slug.values()), 4)),
        ComputedMetric("lexical_load_spikes", spikes),
    )
    return _result(bodies, not spikes, spec, 0, metrics)


# --- semantic criteria: extract or classify with the LLM, decide in code ----------------


def objectives_observable_verbs(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """Every declared objective is phrased with an observable action verb."""
    entry = _entry(profile, "learning_objectives")
    classified, usage = tasks.objectives_classification(profile)
    metrics = (
        _usage_metric("objectives_classification", usage),
        ComputedMetric("objective_bloom_levels", [c.bloom_level for c in classified]),
    )
    if not classified:
        # No non-blank objectives to phrase badly; the counting criterion owns absence.
        return _result(entry, True, spec, metrics=metrics)
    offender = next((c for c in classified if not c.is_observable), None)
    if offender is not None:
        return _result(entry, False, spec, 0, metrics, quote=offender.text)
    return _result(entry, True, spec, metrics=metrics)


def outcomes_present(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """The opening lesson states at least one outcome to the learner."""
    outcomes, usage = tasks.outcomes_extraction(profile)
    body, bodies_entry = tasks.opening_lesson_body(profile)
    metrics = (
        _usage_metric("outcomes_extraction", usage),
        ComputedMetric("stated_outcomes_count", len(outcomes)),
    )
    if outcomes:
        # The statement was grounding-checked: it is a verbatim substring of the body.
        return _result(bodies_entry, True, spec, metrics=metrics, quote=outcomes[0].statement)
    return _result(bodies_entry, False, spec, 0, metrics, quote=_excerpt(body))


def outcomes_observable_verbs(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """Every outcome the opening lesson states uses an observable action verb."""
    outcomes, usage = tasks.outcomes_extraction(profile)
    body, bodies_entry = tasks.opening_lesson_body(profile)
    metrics = (_usage_metric("outcomes_extraction", usage),)
    offender = next((o for o in outcomes if not o.is_observable), None)
    if offender is not None:
        return _result(bodies_entry, False, spec, 0, metrics, quote=offender.statement)
    # All observable — vacuously when the lesson states none, which is `outcomes-present`'s
    # finding to make, not this criterion's.
    quote = outcomes[0].statement if outcomes else _excerpt(body)
    return _result(bodies_entry, True, spec, metrics=metrics, quote=quote)


def objectives_non_decreasing_demand(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """Successive objectives never drop by more than one Bloom level, and are not flat
    across a course long enough to progress."""
    entry = _entry(profile, "learning_objectives")
    classified, usage = tasks.objectives_classification(profile)
    ranks = [c.rank for c in classified]
    metrics = (
        _usage_metric("objectives_classification", usage),
        ComputedMetric("objective_bloom_levels", [c.bloom_level for c in classified]),
    )
    if len(classified) < 2:
        # A single objective is a point: nothing to fall back from, nothing flat.
        return _result(entry, True, spec, metrics=metrics)
    for previous, current in pairwise(classified):
        if current.rank < previous.rank - ALLOWED_BLOOM_DROP:
            return _result(entry, False, spec, 0, metrics, quote=current.text)
    if len(ranks) >= FLAT_MIN_OBJECTIVES and len(set(ranks)) == 1:
        return _result(entry, False, spec, 1, metrics)
    return _result(entry, True, spec, metrics=metrics)


def cognitive_demand_rises_across_the_course(
    spec: CriterionSpec, profile: ProfileData
) -> ExecutorResult:
    """The concepts the core lessons cover grow in sophistication in delivery order —
    local one-level dips allowed, working below the running peak is not, and a long flat
    trajectory is a list rather than a progression."""
    entry = _entry(profile, "lesson_concepts")
    trajectory, usage = tasks.concept_trajectory(profile)
    levels = [lesson.level for lesson in trajectory]
    metrics = (
        _usage_metric("concept_trajectory", usage),
        ComputedMetric("concept_sophistication_levels", levels),
    )
    if len(trajectory) < 2:
        return _result(entry, True, spec, metrics=metrics)
    concept_by_id = {str(record["lessonId"]): record for record in entry.value}
    peak = trajectory[0].level
    for lesson in trajectory[1:]:
        if lesson.level < peak - ALLOWED_SOPHISTICATION_DIP:
            record = concept_by_id.get(lesson.lesson_id, {"lessonId": lesson.lesson_id})
            offending = json.dumps(record, ensure_ascii=False, sort_keys=True)
            return _result(entry, False, spec, 0, metrics, quote=offending)
        peak = max(peak, lesson.level)
    if len(levels) >= FLAT_MIN_CORE_LESSONS and len(set(levels)) == 1:
        return _result(entry, False, spec, 1, metrics)
    return _result(entry, True, spec, metrics=metrics)
