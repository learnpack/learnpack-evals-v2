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
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    judgments,
    measures,
    tasks,
)
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

# "at least 2 distinct earlier lessons outside their own module" — the pass condition's own
# number, not an empirical threshold. It lives here because an executor cannot read a
# structured threshold off the instrument today; if that changes, this is one of the
# constants that should be read rather than retyped.
EARLIER_LESSONS_REACHED = 2

# "at least two thirds", in both continuity criteria — again the pass condition's own number,
# retyped for the same reason. Compared as a fraction rather than a float so the boundary case
# is exact: two of three passes, five of eight does not.
BUILD_RATIO_NUMERATOR = 2
BUILD_RATIO_DENOMINATOR = 3

# What counts as WORKING WITH a concept, and it is deliberately wide (ADR-0047 §4): developing
# it, operating with it as already known, or setting a task on it. `mentions` is out — naming
# earlier material is not building on it — and so is `defines`, which is the course saying
# again what it already said, i.e. starting over rather than building.
#
# The narrower reading, "uses it rather than restates it", was implemented and measured and
# does not survive: over one draft two independent readers found that act in 23 and 29 places
# while six model runs found it in 0 to 9. Narrowing this tuple is not a stricter criterion,
# it is a criterion that measures who is reading.
WORKING_WITH_GROUPS = ("develops", "uses_as_known", "assessed")


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
    """What the task spent, as evidence that travels with the evaluation (ADR-0034).

    `clean_retries` rides along because a verdict that needed a fresh conversation is a
    shifted population, and calibration must be able to tell (ADR-0037 §7)."""
    return ComputedMetric(
        f"llm_{task_id}",
        {
            "model": usage.model,
            "calls": usage.calls,
            "tokens_in": usage.tokens_in,
            "tokens_out": usage.tokens_out,
            "latency_ms": usage.latency_ms,
            "clean_retries": usage.clean_retries,
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
    entry = _entry(profile, "lesson_concept_coverage")
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


# --- judged criteria: the model decides, grounded and against the instrument's words -----
#
# v3's addition. Unlike everything above, the verdict here IS the model's — these pass
# conditions have no mechanical proxy. What keeps them reviewable is that the question is
# the instrument's `pass_condition` verbatim (never retyped here), the answer carries a
# quote checked against the text shown, and the failure mode is chosen from the criterion's
# own declared list. See `judgments.py`.


def _judged(
    entry: ProfileEntryData,
    judged: judgments.Judgement,
    spec: CriterionSpec,
    task_id: str,
    extra_metrics: tuple[ComputedMetric, ...] = (),
) -> ExecutorResult:
    """One judged criterion as an `ExecutorResult`: the judge's own quotes are the evidence.

    The reason travels as a metric rather than as the quote: a report's quote must be
    something a reader can find in the course (ADR-0009), and the reason is the judge's
    prose about it.

    A judgement may rest on several passages, and `ExecutorResult` carries one quote. The
    FIRST is the quote — each is already a continuous span of the source, so the one a
    report shows is verifiable on its own — and the rest travel as a metric rather than
    being concatenated into something the course does not contain contiguously.

    How close the vote was travels too: a criterion answered 2-1 is one whose threshold the
    instrument left unwritten, and that is worth as much to whoever reads the run as the
    verdict itself.
    """
    verdict = judged.verdict
    metrics = (
        _usage_metric(task_id, judged.usage),
        ComputedMetric(
            f"judgment_agreement_{task_id}",
            {"samples": judged.samples, "agreed": judged.agreed},
        ),
        ComputedMetric(f"judgment_{task_id}", verdict.reason),
        *(
            (ComputedMetric(f"evidence_{task_id}", list(verdict.evidence)),)
            if verdict.evidence
            else ()
        ),
        *extra_metrics,
    )
    return _result(
        entry,
        verdict.passed,
        spec,
        verdict.failure_mode_index,
        metrics,
        quote=verdict.evidence[0] if verdict.evidence else None,
    )


def opening_lesson_connects_backwards(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """The opening relates the new material to what the learner already knows."""
    body, entry = tasks.opening_lesson_body(profile)
    judged = judgments.judge(
        profile,
        spec,
        task_id="opening_connects_backwards",
        source_description="the body of the FIRST lesson by declared position",
        corpus=body,
    )
    return _judged(entry, judged, spec, "opening_connects_backwards")


def closing_lesson_integrates(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """The closing relates what was learned across the course into a connected whole."""
    body, entry = judgments.closing_lesson_body(profile)
    judged = judgments.judge(
        profile,
        spec,
        task_id="closing_integrates",
        source_description="the body of the LAST lesson by declared position",
        corpus=body,
    )
    return _judged(entry, judged, spec, "closing_integrates")


def closing_lesson_projects_forward(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """The closing says what the learner can now do and where it leads."""
    body, entry = judgments.closing_lesson_body(profile)
    judged = judgments.judge(
        profile,
        spec,
        task_id="closing_projects_forward",
        source_description="the body of the LAST lesson by declared position",
        corpus=body,
    )
    return _judged(entry, judged, spec, "closing_projects_forward")


def arc_character(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """The first lesson introduces the course and the last one closes it.

    Judged over BOTH frame bodies in one question because the criterion asserts about the
    pair: an opening that frames and a course that simply stops is one finding, not two.
    Its own call rather than a share of the two single-lesson judgements, because an
    executor receives only its own `CriterionSpec` and a shared question would have to
    retype a sibling criterion's normative text.
    """
    bodies = _entry(profile, "lesson_bodies")
    judged = judgments.judge(
        profile,
        spec,
        task_id="arc_character",
        source_description="the first and last lessons by declared position",
        corpus=judgments.arc_corpus(profile),
    )
    return _judged(bodies, judged, spec, "arc_character")


def _cited_task(offerings: list[dict[str, Any]], numbers: tuple[int, ...]) -> str:
    """The prompt of the first task cited, as the course writes it.

    Since v12 the model cites tasks by number and never transcribes them, so the passage a
    report shows is fetched here rather than copied by the judge — the course's own text, not
    the label this package puts around it (ADR-0009).
    """
    for number in numbers:
        if 0 <= number < len(offerings):
            return str(offerings[number].get("prompt") or "")
    return ""


def _objective_outcome(profile: ProfileData, objective_id: str) -> str:
    return next(
        (
            str(objective["outcome"])
            for objective in _entry(profile, "declared_objectives").value
            if str(objective["id"]) == objective_id
        ),
        "",
    )


def every_objective_has_an_assessment_item(
    spec: CriterionSpec, profile: ProfileData
) -> ExecutorResult:
    """Every declared objective is measured by at least one task the draft offers.

    The verdict is CODE's: the model supplies the mapping (which tasks bear on which
    objective) and "every objective has at least one" is arithmetic over it. Only the
    matching needed a judge.

    Two metrics answer the question this criterion's widening raises (ADR-0046): how much of
    the coverage rests on tasks the draft only PROPOSES, and how much assessment of each kind
    there was to map. A criterion that passes only because every match is a proposal is a
    different finding from one that passes on delivered work, and the report should not need
    a trace to tell them apart.
    """
    entry = _entry(profile, "declared_objectives")
    offerings = list(_entry(profile, "assessment_offerings").value)
    mappings, usage = judgments.assessment_mapping(profile)
    unmeasured = [mapping for mapping in mappings if not mapping.task_indices]

    def proposed_only(mapping: judgments.ObjectiveMapping) -> bool:
        measured = [offerings[index] for index in mapping.task_indices if index < len(offerings)]
        return bool(measured) and all(task.get("status") == "proposed" for task in measured)

    metrics = (
        _usage_metric("assessment_mapping", usage),
        ComputedMetric("objectives_measured_count", len(mappings) - len(unmeasured)),
        ComputedMetric("objectives_unmeasured", [mapping.objective_id for mapping in unmeasured]),
        ComputedMetric(
            "objectives_measured_by_proposal_only",
            [mapping.objective_id for mapping in mappings if proposed_only(mapping)],
        ),
        ComputedMetric(
            "assessment_offered",
            {
                "delivered": sum(1 for o in offerings if o.get("status") != "proposed"),
                "proposed": sum(1 for o in offerings if o.get("status") == "proposed"),
            },
        ),
    )
    if unmeasured:
        # Built with `_result` rather than `_judged` on purpose: nothing here was voted on,
        # so an agreement metric would report a vote that never happened.
        offender = unmeasured[0]
        return _result(
            entry,
            False,
            spec,
            0,
            (*metrics, ComputedMetric("judgment_assessment_mapping", offender.reason)),
            # An objective nothing measures has no task to quote, so the citation is the
            # objective's own words — the finding IS about that objective.
            quote=_objective_outcome(profile, offender.objective_id),
        )
    quote = _cited_task(offerings, mappings[0].task_indices) if mappings else entry.quote or ""
    return _result(entry, True, spec, metrics=metrics, quote=quote)


def assessment_matches_the_declared_verification(
    spec: CriterionSpec, profile: ProfileData
) -> ExecutorResult:
    """The tasks measuring an objective ask for what its declared verification describes.

    Reads the mapping the previous criterion paid for (memoized), narrows it in code to the
    objectives the criterion is about — those that declare a verification AND have tasks
    bearing on them — and judges them ONE BY ONE, adding the answers up here.

    That last part is v12 and it is the whole fix. Asked for a single verdict over every
    objective at once, the judge did the adding itself and did it badly: one sample wrote
    "satisfied except obj-3, whose tasks are recognition items" and answered TRUE, and repeats
    that agreed on a failure named different objectives and picked different failure modes.
    Aggregation is code's job everywhere else in this package; here it was the model's only
    by accident of the answer shape. Now the criterion fails when ANY objective fails, the
    failure mode is that objective's, and each objective carries its own reason.
    """
    entry = _entry(profile, "declared_objectives")
    offerings = list(_entry(profile, "assessment_offerings").value)
    mappings, mapping_usage = judgments.assessment_mapping(profile)
    case = judgments.verification_corpus(profile, mappings)
    if case is None:
        # Nothing the criterion is about: no objective both declares a verification and has
        # a task bearing on it. Vacuously satisfied — the objectives with no task at all
        # are the previous criterion's finding, not this one's.
        return _result(
            entry,
            True,
            spec,
            metrics=(
                _usage_metric("assessment_mapping", mapping_usage),
                ComputedMetric("verification_pairs_judged", 0),
            ),
        )
    corpus, citable = case
    judged = judgments.judge_per_objective(
        profile,
        spec,
        task_id="assessment_verification_match",
        source_description="the objectives that declare how they would be verified, with the "
        "assessment tasks found to measure them",
        corpus=corpus,
        citable=citable,
    )
    metrics = (
        _usage_metric("assessment_verification_match", judged.usage),
        _usage_metric("assessment_mapping", mapping_usage),
        ComputedMetric(
            "judgment_agreement_assessment_verification_match",
            {"samples": judged.samples, "agreed": judged.agreed},
        ),
        ComputedMetric("verification_pairs_judged", len(judged.verdicts)),
        ComputedMetric(
            "verification_by_objective",
            [
                {
                    "objectiveId": verdict.objective_id,
                    "satisfied": verdict.satisfied,
                    "reason": verdict.reason,
                    "taskNumbers": list(verdict.task_numbers),
                }
                for verdict in judged.verdicts
            ],
        ),
        # Which objectives each sample failed, not just how many samples agreed: samples that
        # agree on the verdict and name different objectives disagree about the facts, and
        # samples that name the same one and split disagree about the bar. Only the second is
        # a bug report about the instrument, and the verdict alone cannot tell them apart.
        ComputedMetric(
            "verification_failed_by_sample", [list(failed) for failed in judged.failed_by_sample]
        ),
    )
    if judged.failed:
        offender = judged.failed[0]
        return _result(
            entry,
            False,
            spec,
            offender.failure_mode_index,
            metrics,
            quote=_cited_task(offerings, offender.task_numbers),
        )
    return _result(
        entry,
        True,
        spec,
        metrics=metrics,
        quote=_cited_task(offerings, judged.verdicts[0].task_numbers),
    )


def assessment_retrieves_earlier_taught_material(
    spec: CriterionSpec, profile: ProfileData
) -> ExecutorResult:
    """The offered tasks collectively draw on at least 2 earlier lessons outside their module.

    Extraction plus a count, not a judgement: the model reports which lessons each task
    draws on (constrained to identifiers the plan declares, so it cannot invent one) and
    the reach rule is arithmetic here, where it can be read. A proposed exercise reaches back
    exactly as a delivered question does — what the learner must have studied to do it does
    not depend on who materializes it.
    """
    entry = _entry(profile, "assessment_offerings")
    reaches, usage = judgments.assessment_reach(profile)
    offerings = list(entry.value)
    ordered = tasks.ordered_inventory(profile)
    position_by_id = {str(lesson["lessonId"]): index for index, lesson in enumerate(ordered)}

    reached: set[str] = set()
    for reach in reaches:
        if reach.index >= len(offerings):
            continue
        own_id = str(offerings[reach.index].get("lessonId"))
        own_position = position_by_id.get(own_id)
        own_module = _module(own_id)
        for referenced in reach.references:
            referenced_position = position_by_id.get(referenced)
            if own_position is None or referenced_position is None:
                continue
            if referenced_position < own_position and _module(referenced) != own_module:
                reached.add(referenced)

    metrics = (
        _usage_metric("assessment_reach", usage),
        ComputedMetric("assessment_reaches_back_to", sorted(reached)),
    )
    return _result(entry, len(reached) >= EARLIER_LESSONS_REACHED, spec, 0, metrics)


# --- the continuity criteria (v13): one concept map, two verdicts -----------------------
#
# Both read the same map (`tasks.concept_map`, memoized), and both decide the same way: the
# model reported local acts with quotes, and everything about ORDER is computed here. Where a
# concept is introduced is `min(position)` over the lessons that state it — arithmetic, never
# asked — which is what lets a verdict rest on this at all (ADR-0047 §6).
#
# Note what is NOT read: the plan's own concept-to-lesson assignment. It is `defines` in the
# prose that anchors both criteria, because a draft was measured whose `X.0` lesson does the
# work its `X.1` lesson is planned to teach — an introduction read off the plan is wrong
# exactly where the draft is interesting.

_Lesson = tuple[str, int, str | None]


def _map_metrics(found: tasks.ConceptMap, usage: LlmUsage) -> tuple[ComputedMetric, ...]:
    """What the map cost, and how complete it is.

    The second one travels because a verdict computed over a map that lost rows is a different
    verdict, and a reader is entitled to tell the two apart.
    """
    return (
        _usage_metric("concept_map", usage),
        ComputedMetric(
            "concept_map_coverage",
            {
                "concepts": found.concepts,
                "lessons": found.lessons,
                "appearances": len(found.appearances),
                "calls": found.calls,
                "dropped": len(found.dropped),
            },
        ),
    )


def _introduced_at(found: tasks.ConceptMap) -> dict[int, int]:
    """The position of the lesson that introduces each concept: the earliest to state it.

    The deterministic anchor. A concept several lessons state is not a contradiction but a
    finding — the first is the introduction and every later one is the course defining again
    what it had already defined — and which is which is decided here, by `min`.
    """
    first: dict[int, int] = {}
    for row in found.appearances:
        if row.group != tasks.DEFINES_GROUP:
            continue
        seen = first.get(row.concept_index)
        if seen is None or row.lesson_position < seen:
            first[row.concept_index] = row.lesson_position
    return first


def _by_lesson(
    found: tasks.ConceptMap, groups: tuple[str, ...]
) -> dict[str, list[tasks.ConceptAppearance]]:
    rows: dict[str, list[tasks.ConceptAppearance]] = {}
    for row in found.appearances:
        if row.group in groups:
            rows.setdefault(row.lesson_id, []).append(row)
    return rows


def _ordered_lessons(profile: ProfileData) -> list[_Lesson]:
    """Every lesson as (id, position, module) in delivery order — the same order the map's
    positions were assigned in, because both come from `tasks.ordered_inventory`."""
    return [
        (str(lesson["lessonId"]), position, _module(str(lesson["lessonId"])))
        for position, lesson in enumerate(tasks.ordered_inventory(profile))
    ]


def _meets_ratio(hits: int, of: int) -> bool:
    """Two thirds, as a fraction rather than a float: 2 of 3 passes, 5 of 8 does not."""
    return hits * BUILD_RATIO_DENOMINATOR >= of * BUILD_RATIO_NUMERATOR


def _module_order(module: str | None) -> tuple[bool, str]:
    return (module is None, module or "")


def _body_excerpt(profile: ProfileData, lesson_id: str) -> str:
    """Enough of the failing lesson to verify the absence, without dumping a whole body."""
    bodies = profile.entries["lesson_bodies"]
    for lesson in bodies.value:
        if str(lesson.get("lessonId")) == lesson_id:
            return _excerpt(str(lesson.get("body") or ""))
    return bodies.quote or ""


def lessons_build_within_their_module(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """Within a module, later lessons work with what the module already taught.

    The population is every lesson that follows the first lesson of its own module, so a module
    of one lesson contributes nobody — it has no interior to build across. Two thirds of that
    population must work with a concept an earlier lesson OF THAT SAME MODULE introduces, and
    no two consecutive of them may both fail.

    "Consecutive" is read within a module rather than across the whole population. Two lessons
    in different modules are not consecutive in any sense this claim is about — it is entirely
    about a module's interior — and the criterion's own third failure mode says as much:
    *a stretch of consecutive lessons inside one module*.
    """
    entry = _entry(profile, "lesson_bodies")
    found, usage = tasks.concept_map(profile)

    lessons = _ordered_lessons(profile)
    introduced_at = _introduced_at(found)
    module_at = {position: module for _, position, module in lessons}
    worked = _by_lesson(found, WORKING_WITH_GROUPS)
    restated = _by_lesson(found, (tasks.DEFINES_GROUP,))

    by_module: dict[str | None, list[_Lesson]] = {}
    for lesson in lessons:
        by_module.setdefault(lesson[2], []).append(lesson)

    def from_its_own_module(
        rows: dict[str, list[tasks.ConceptAppearance]], lesson: _Lesson
    ) -> tasks.ConceptAppearance | None:
        lesson_id, position, module = lesson
        for row in rows.get(lesson_id, []):
            introduction = introduced_at.get(row.concept_index)
            if introduction is None or introduction >= position:
                continue
            if module_at.get(introduction) == module:
                return row
        return None

    hits: list[tasks.ConceptAppearance] = []
    total = 0
    consecutive_failure = False
    first_failure: _Lesson | None = None
    for module in sorted(by_module, key=_module_order):
        previous_failed = False
        for lesson in by_module[module][1:]:
            total += 1
            evidence = from_its_own_module(worked, lesson)
            if evidence is not None:
                hits.append(evidence)
                previous_failed = False
                continue
            first_failure = first_failure or lesson
            consecutive_failure = consecutive_failure or previous_failed
            previous_failed = True

    metrics = (
        *_map_metrics(found, usage),
        ComputedMetric("module_internal_build", {"of": total, "built": len(hits)}),
    )
    # Nothing was asked of the course, so nothing failed: either no module has an interior, or
    # there was no map to build. The second case is a plan that declares no concept at all, and
    # a fail derived from that would be a claim about the course made from the absence of a
    # datum (ADR-0021). An EMPTY map that was asked for is a different thing and does fail —
    # `calls` is what tells the two apart, and `concept_map_coverage` carries it to the report.
    if total == 0 or found.calls == 0:
        return _result(entry, True, spec, metrics=metrics, quote=_passing_quote(entry, hits))
    if _meets_ratio(len(hits), total) and not consecutive_failure:
        return _result(entry, True, spec, metrics=metrics, quote=_passing_quote(entry, hits))

    assert first_failure is not None  # failing either part implies at least one failure
    restatement = from_its_own_module(restated, first_failure)
    if consecutive_failure:
        failure_index = 2
    elif restatement is not None:
        # It did touch what its module taught, and what it did was say again what it is.
        failure_index = 1
    else:
        failure_index = 0
    quote = (
        restatement.quote
        if failure_index == 1 and restatement is not None
        else _body_excerpt(profile, first_failure[0])
    )
    return _result(entry, False, spec, failure_index, metrics, quote=quote)


def modules_build_on_earlier_modules(spec: CriterionSpec, profile: ProfileData) -> ExecutorResult:
    """Later modules work with what earlier modules taught.

    The population is the thematic modules after the first one — module 00 is the course-level
    opening slot this format reserves, so it is not one of them, and a course without that slot
    counts every module. Two thirds of the population must hold a lesson working with a concept
    an EARLIER module introduces.
    """
    entry = _entry(profile, "lesson_bodies")
    found, usage = tasks.concept_map(profile)

    lessons = _ordered_lessons(profile)
    introduced_at = _introduced_at(found)
    module_at = {position: module for _, position, module in lessons}
    worked = _by_lesson(found, WORKING_WITH_GROUPS)
    named = _by_lesson(found, ("mentions",))

    ordered_modules: list[str | None] = []
    members: dict[str | None, list[_Lesson]] = {}
    for lesson in lessons:
        if lesson[2] not in ordered_modules:
            ordered_modules.append(lesson[2])
        members.setdefault(lesson[2], []).append(lesson)
    thematic = [module for module in ordered_modules if module != "00"] or ordered_modules

    def reaches_back(
        rows: dict[str, list[tasks.ConceptAppearance]], module: str | None
    ) -> tasks.ConceptAppearance | None:
        for lesson_id, position, _ in members.get(module, []):
            for row in rows.get(lesson_id, []):
                introduction = introduced_at.get(row.concept_index)
                if introduction is None or introduction >= position:
                    continue
                if module_at.get(introduction) != module:
                    return row
        return None

    candidates = thematic[1:]
    hits = [row for module in candidates if (row := reaches_back(worked, module)) is not None]
    metrics = (
        *_map_metrics(found, usage),
        ComputedMetric("cross_module_build", {"of": len(candidates), "built": len(hits)}),
    )
    # A course of one thematic module has nothing to build across, and a plan that declares no
    # concept was never asked — the same two vacuous cases as the criterion above, for the same
    # reason.
    if not candidates or found.calls == 0:
        return _result(entry, True, spec, metrics=metrics, quote=_passing_quote(entry, hits))
    if _meets_ratio(len(hits), len(candidates)):
        return _result(entry, True, spec, metrics=metrics, quote=_passing_quote(entry, hits))

    failing = [module for module in candidates if reaches_back(worked, module) is None]
    # A module that names earlier material without doing anything with it is the second failure
    # mode the criterion declares; one that carries nothing back at all is the first.
    referred = next(
        (row for module in failing if (row := reaches_back(named, module)) is not None), None
    )
    quote = (
        referred.quote
        if referred is not None
        else _body_excerpt(profile, members[failing[0]][0][0])
    )
    return _result(entry, False, spec, 1 if referred is not None else 0, metrics, quote=quote)


def _passing_quote(entry: ProfileEntryData, hits: list[tasks.ConceptAppearance]) -> str:
    """A passing verdict quotes the course rather than the profile's canonical entry: the first
    place the criterion actually found the course building on itself."""
    return hits[0].quote if hits else (entry.quote or "")
