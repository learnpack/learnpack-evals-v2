"""Executors of the `drafts-structural` assessor — pure code over checked profile data.

A COPY of `structural` v1's executors, restricted to the criteria of the `course-drafts-qa`
lineage, not an import: sharing the functions would tie two assessors' identities together
(ADR-0016 gives an algorithm its identity through the assessor's version, and a change to a
shared module would silently change both artifacts). Editing this file is a new version of
`drafts-structural` and says nothing about `structural`. The two executors whose criteria
the drafts instrument deliberately dropped (`lessons_with_activities`,
`lesson_type_matches_delivery` — both need `lesson_activities`, which a draft does not
have) are not copied.

Each executor realizes one criterion's pass condition (ADR-0016: the mapping
criterion -> executor is this assessor's internal detail, never the instrument's).
Profiles arrive with their value domains verified (ADR-0020), so shapes are assumed.
Evidence discipline: every result quotes the profile entry it judged (the entry's quote
is the adapter's canonical, verifiable citation of the package — ADR-0009).

Failure modes are chosen BY POSITION from the criterion's declared list — the wording
lives in the instrument only. Reordering an instrument's failure modes is a normative
change this selection follows blindly; the human layer 2 (ADR-0015) verifies
norm/realization consistency, and any undeclared mode is rejected at derivation time.

Module mechanics mirror the lesson-id convention the instrument's data requirements
describe: lesson ids parse as 'NN.M', module = the 'NN' prefix, module 00 is the
course-level introduction slot and the last lesson (by declared position) is the closing
slot.
"""

import re
import statistics
from typing import Any

from app.modules.evaluation.domain.model import (
    ComputedMetric,
    CriterionSpec,
    ExecutorResult,
    ProfileData,
    ProfileEntryData,
)
from app.modules.evaluation.infrastructure.assessors.drafts_structural import measures

_LESSON_ID = re.compile(r"^(\d{2})\.(\d+)$")
_AUDIENCE_BOILERPLATE = frozenset({"everyone", "anyone", "anyone interested"})

# How far above its own course's median a lesson's lexical load may sit. Empirical, set
# against the frozen corpus, and larger than the disagreement between reasonable
# implementations of the measure — otherwise the verdict would be decided by the
# implementation rather than by the text. The evidence is in docs/MEASUREMENT.md; do not
# move it without redoing that work.
LEXICAL_LOAD_SPIKE = 0.20


def _entry(profile: ProfileData, data_requirement_id: str) -> ProfileEntryData:
    return profile.entries[data_requirement_id]


def _result(
    entry: ProfileEntryData,
    passed: bool,
    spec: CriterionSpec,
    failure_index: int | None = None,
    metrics: tuple[ComputedMetric, ...] = (),
) -> ExecutorResult:
    return ExecutorResult(
        passed=passed,
        quote=entry.quote or "",
        locator=entry.locator,
        failure_mode=None if passed else spec.failure_modes[failure_index or 0],
        metrics=metrics,
    )


# --- declaration criteria --------------------------------------------------------------


def objectives_min_count(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """At least 2 non-blank learning objectives declared."""
    entry = _entry(profile, "learning_objectives")
    declared = [o for o in entry.value if str(o).strip()]
    # Named `declared_objectives_count`, NOT `declared_objectives` (structural v1's name):
    # this lineage mints a data requirement with that exact id — the objectives themselves,
    # each with its declared verification — and a report line `declared_objectives: 5` must
    # not be ambiguous between a count and a list. The rename is legal here because this is
    # a new artifact; inside `structural` it would cost that assessor a version for a
    # cosmetic reason. `learning_objectives` (this executor's input) keeps being supplied
    # by the adapter on purpose — published versions of this lineage require it.
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


# --- structural criteria over the lesson index -----------------------------------------


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


# --- the lexical-load measure ----------------------------------------------------------


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
