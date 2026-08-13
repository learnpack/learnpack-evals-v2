"""The semantic tasks of `drafts-hybrid` — extraction and classification, never verdicts.

Each task asks the model for DATA (statements, verbs, levels) and the executors turn that
data into pass/fail deterministically (counts, order checks) — the extract-then-decide
half of the spectrum, the cheap half the abstention notes said to build first. The model
never chooses an outcome, so the judge's decision rule stays in reviewable code.

Everything here is identity (ADR-0034): the model each task pins, the sampling
parameters, the validation contracts. `SOURCE_CONFIG` carries the model ids, so changing
one without a VERSION bump is refused at ratification. Changing a model IS a version bump
by design — calibration does not transfer between judges.

Tasks are memoized per profile: two criteria deliberately read one extraction (the
instrument writes them as separate criteria over the same datum), profiles are immutable,
and paying twice for one question would be pure waste. `clear_task_cache()` exists for
tests and for long-lived processes that want the memory back.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.evaluation.domain.model import ExecutionFailure, ProfileData, ProfileEntryData
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import prompts, runtime
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.structured_output import (
    LlmUsage,
    request_structured_output,
)
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError

# One model per task, pinned here (ADR-0034: the model id's namespace names the provider).
# Swapping any of these is a new version of `drafts-hybrid`.
OUTCOMES_EXTRACTION_MODEL = "deepseek/deepseek-v4-flash-0731"
OBJECTIVES_CLASSIFICATION_MODEL = "deepseek/deepseek-v4-flash-0731"
CONCEPT_TRAJECTORY_MODEL = "deepseek/deepseek-v4-flash-0731"

# Deterministic-as-the-provider-allows: these are classification tasks, not writing tasks.
TEMPERATURE = 0.0

# No thinking out loud. A reasoning model bills its thinking as output tokens, so it
# competes with the answer for `MAX_OUTPUT_TOKENS` — and on these tasks it wins: the
# calibration runs of v1 recorded 2048–2325 reasoning tokens and no answer at all,
# every time. Both disable fields are sent (v7) because upstreams honor different ones:
# OpenRouter documents `effort` for OpenAI/Grok models, not this family, and the first
# v6 calibration met two upstreams that reasoned anyway — one billed 3,491 output tokens
# for a 60-token answer, the other returned its whole reasoning and a null answer.
# `exclude: true` is deliberately NOT the tool: it would only hide the thinking from the
# response while still generating and paying for it — the same failure with less evidence.
REASONING = {"effort": "none", "enabled": False}

# Room for the answer even where reasoning happens anyway (not every provider honors
# `effort`). Extraction over one lesson body answers in the low hundreds of tokens, so
# this is a ceiling, not a spend: what is not emitted is not billed. The old 2048 was
# below what the thinking alone consumed.
MAX_OUTPUT_TOKENS = 8000

# Revised Bloom, in demand order — rank 1 is `remember`, rank 6 is `create`.
BLOOM_LEVELS = ("remember", "understand", "apply", "analyze", "evaluate", "create")
BLOOM_RANK = {name: rank for rank, name in enumerate(BLOOM_LEVELS, start=1)}


@dataclass(frozen=True)
class OutcomeStatement:
    """One promise the opening lesson makes to the learner, quoted verbatim."""

    statement: str
    verb: str
    is_observable: bool


@dataclass(frozen=True)
class ObjectiveClassification:
    """One declared objective, classified — text carried so quotes stay ours."""

    text: str
    verb: str
    is_observable: bool
    bloom_level: str

    @property
    def rank(self) -> int:
        return BLOOM_RANK[self.bloom_level]


@dataclass(frozen=True)
class LessonSophistication:
    """One core lesson's demanded sophistication, 1–5, keyed by the plan's lesson id."""

    lesson_id: str
    level: int


# --- memoization ------------------------------------------------------------------------

_cache: dict[tuple[str, UUID], tuple[Any, LlmUsage] | ExecutionFailure] = {}


def clear_task_cache() -> None:
    _cache.clear()


def _memoized(
    task_id: str, profile: ProfileData, run: Callable[[], tuple[Any, LlmUsage]]
) -> tuple[Any, LlmUsage]:
    """Successes AND typed failures are cached: a task feeds several criteria, and all of
    them must see the same answer — or the same failure, without re-asking the model a
    question that just degenerated (ADR-0037 §2). Only `ExecutionFailure` is cached; a bug
    propagates every time."""
    key = (task_id, profile.profile_id)
    if key not in _cache:
        try:
            _cache[key] = run()
        except ExecutionFailure as exc:
            _cache[key] = exc
            raise
    cached = _cache[key]
    if isinstance(cached, ExecutionFailure):
        raise cached
    return cached


# --- reading the profile (structure decided here, never by the model) -------------------


def ordered_inventory(profile: ProfileData) -> list[dict[str, Any]]:
    entry = profile.entries["lesson_inventory"]
    lessons = [dict(lesson) for lesson in entry.value]

    def declared_order(lesson: dict[str, Any]) -> float:
        position = lesson.get("position")
        return float(position) if position is not None else float("inf")

    return sorted(lessons, key=declared_order)


def opening_lesson_body(profile: ProfileData) -> tuple[str, ProfileEntryData]:
    """The body of the first lesson by declared position, and the entry it came from."""
    bodies = profile.entries["lesson_bodies"]
    ordered = ordered_inventory(profile)
    if not ordered:
        raise AssessorExecutionError(
            "the lesson inventory is empty: no opening lesson to read", kind="profile"
        )
    opening_id = str(ordered[0]["lessonId"])
    for lesson in bodies.value:
        if str(lesson.get("lessonId")) == opening_id:
            return str(lesson["body"]), bodies
    raise AssessorExecutionError(
        f"the profile carries no body for the opening lesson '{opening_id}' — "
        "a broken package, not a finding about its pedagogy",
        kind="profile",
    )


# --- task: outcomes extraction ----------------------------------------------------------


def outcomes_extraction(profile: ProfileData) -> tuple[list[OutcomeStatement], LlmUsage]:
    """The outcome statements the opening lesson makes, each grounded verbatim in it."""

    def run() -> tuple[list[OutcomeStatement], LlmUsage]:
        body, _ = opening_lesson_body(profile)
        payload, usage = request_structured_output(
            runtime.get_client(),
            task_id="outcomes_extraction",
            model=OUTCOMES_EXTRACTION_MODEL,
            system_prompt=prompts.OUTCOMES_EXTRACTION_SYSTEM,
            user_prompt=prompts.OUTCOMES_EXTRACTION_USER.substitute(body=body),
            validate=lambda answer: _validate_outcomes(answer, body),
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
            reasoning=REASONING,
        )
        outcomes = [
            OutcomeStatement(
                statement=str(item["statement"]).strip(),
                verb=str(item["verb"]),
                is_observable=bool(item["is_observable"]),
            )
            for item in payload["outcomes"]
        ]
        return outcomes, usage

    result, usage = _memoized("outcomes_extraction", profile, run)
    return list(result), usage


def _validate_outcomes(answer: Any, body: str) -> list[str]:
    violations = _shape_violations(answer, "outcomes")
    if violations:
        return violations
    for position, item in enumerate(answer["outcomes"]):
        label = f"outcomes[{position}]"
        if not isinstance(item, dict):
            violations.append(f"{label} must be an object")
            continue
        statement = item.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            violations.append(f"{label}.statement must be a non-empty string")
        elif statement.strip() not in body:
            # The grounding rule: a citation that is not in the source is not evidence.
            violations.append(
                f"{label}.statement is not a verbatim quote from the lesson — copy the "
                f"sentence character-for-character (got: {statement.strip()[:120]!r})"
            )
        if not isinstance(item.get("verb"), str) or not str(item.get("verb")).strip():
            violations.append(f"{label}.verb must be a non-empty string")
        if not isinstance(item.get("is_observable"), bool):
            violations.append(f"{label}.is_observable must be true or false")
    return violations


# --- task: objectives classification ----------------------------------------------------


def objectives_classification(
    profile: ProfileData,
) -> tuple[list[ObjectiveClassification], LlmUsage]:
    """Each declared (non-blank) objective with its verb, observability and Bloom level."""

    def run() -> tuple[list[ObjectiveClassification], LlmUsage]:
        entry = profile.entries["learning_objectives"]
        texts = [str(objective).strip() for objective in entry.value if str(objective).strip()]
        if not texts:
            # Nothing to classify is not a failure: the counting criterion owns absence.
            return [], LlmUsage(
                model=OBJECTIVES_CLASSIFICATION_MODEL,
                calls=0,
                tokens_in=0,
                tokens_out=0,
                latency_ms=0,
            )
        listed = "\n".join(f"{index}: {text}" for index, text in enumerate(texts))
        payload, usage = request_structured_output(
            runtime.get_client(),
            task_id="objectives_classification",
            model=OBJECTIVES_CLASSIFICATION_MODEL,
            system_prompt=prompts.OBJECTIVES_CLASSIFICATION_SYSTEM,
            user_prompt=prompts.OBJECTIVES_CLASSIFICATION_USER.substitute(objectives=listed),
            validate=lambda answer: _validate_objectives(answer, expected=len(texts)),
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
            reasoning=REASONING,
        )
        by_index = {int(item["index"]): item for item in payload["objectives"]}
        classified = [
            ObjectiveClassification(
                text=texts[index],
                verb=str(by_index[index]["verb"]),
                is_observable=bool(by_index[index]["is_observable"]),
                bloom_level=str(by_index[index]["bloom_level"]),
            )
            for index in range(len(texts))
        ]
        return classified, usage

    result, usage = _memoized("objectives_classification", profile, run)
    return list(result), usage


def _validate_objectives(answer: Any, expected: int) -> list[str]:
    violations = _shape_violations(answer, "objectives")
    if violations:
        return violations
    seen: set[int] = set()
    for position, item in enumerate(answer["objectives"]):
        label = f"objectives[{position}]"
        if not isinstance(item, dict):
            violations.append(f"{label} must be an object")
            continue
        index = item.get("index")
        if not isinstance(index, int) or not 0 <= index < expected:
            violations.append(f"{label}.index must be an integer between 0 and {expected - 1}")
        elif index in seen:
            violations.append(f"{label}.index {index} appears more than once")
        else:
            seen.add(index)
        if not isinstance(item.get("verb"), str) or not str(item.get("verb")).strip():
            violations.append(f"{label}.verb must be a non-empty string")
        if not isinstance(item.get("is_observable"), bool):
            violations.append(f"{label}.is_observable must be true or false")
        if item.get("bloom_level") not in BLOOM_LEVELS:
            violations.append(f"{label}.bloom_level must be one of: {', '.join(BLOOM_LEVELS)}")
    if not violations and len(seen) != expected:
        missing = sorted(set(range(expected)) - seen)
        violations.append(f"missing an entry for objective index(es): {missing}")
    return violations


# --- task: concept trajectory -----------------------------------------------------------


def concept_trajectory(profile: ProfileData) -> tuple[list[LessonSophistication], LlmUsage]:
    """Sophistication per CORE lesson, in delivery order — opening and closing excluded,
    exactly as the criterion's pass condition excludes them. The exclusion happens here,
    in code, so the model never decides what counts as frame."""

    def run() -> tuple[list[LessonSophistication], LlmUsage]:
        ordered = ordered_inventory(profile)
        core = ordered[1:-1] if len(ordered) > 2 else []
        if len(core) < 2:
            # One core lesson is a point, not a trajectory: nothing to classify.
            return [], LlmUsage(
                model=CONCEPT_TRAJECTORY_MODEL, calls=0, tokens_in=0, tokens_out=0, latency_ms=0
            )
        concepts = profile.entries["lesson_concepts"]
        concept_by_id = {
            str(record["lessonId"]): record.get("concept") for record in concepts.value
        }
        plan_lines = "\n".join(
            json.dumps(
                {
                    "lessonId": str(lesson["lessonId"]),
                    "title": lesson.get("title"),
                    "type": lesson.get("type"),
                    "concept": concept_by_id.get(str(lesson["lessonId"])),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            for lesson in core
        )
        core_ids = [str(lesson["lessonId"]) for lesson in core]
        payload, usage = request_structured_output(
            runtime.get_client(),
            task_id="concept_trajectory",
            model=CONCEPT_TRAJECTORY_MODEL,
            system_prompt=prompts.CONCEPT_TRAJECTORY_SYSTEM,
            user_prompt=prompts.CONCEPT_TRAJECTORY_USER.substitute(plan=plan_lines),
            validate=lambda answer: _validate_trajectory(answer, expected_ids=core_ids),
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
            reasoning=REASONING,
        )
        by_id = {str(item["lessonId"]): int(item["level"]) for item in payload["lessons"]}
        trajectory = [
            LessonSophistication(lesson_id=lesson_id, level=by_id[lesson_id])
            for lesson_id in core_ids
        ]
        return trajectory, usage

    result, usage = _memoized("concept_trajectory", profile, run)
    return list(result), usage


def _validate_trajectory(answer: Any, expected_ids: list[str]) -> list[str]:
    violations = _shape_violations(answer, "lessons")
    if violations:
        return violations
    seen: set[str] = set()
    expected = set(expected_ids)
    for position, item in enumerate(answer["lessons"]):
        label = f"lessons[{position}]"
        if not isinstance(item, dict):
            violations.append(f"{label} must be an object")
            continue
        lesson_id = item.get("lessonId")
        if not isinstance(lesson_id, str) or lesson_id not in expected:
            violations.append(
                f"{label}.lessonId must be one of the given identifiers (got {lesson_id!r})"
            )
        elif lesson_id in seen:
            violations.append(f"{label}.lessonId {lesson_id!r} appears more than once")
        else:
            seen.add(lesson_id)
        level = item.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 5:
            violations.append(f"{label}.level must be an integer from 1 to 5")
    if not violations and seen != expected:
        missing = sorted(expected - seen)
        violations.append(f"missing an entry for lesson id(s): {missing}")
    return violations


# --- shared shape check -----------------------------------------------------------------


def _shape_violations(answer: Any, key: str) -> list[str]:
    if not isinstance(answer, dict):
        return [f'the answer must be a JSON object with a "{key}" array']
    if not isinstance(answer.get(key), list):
        return [f'"{key}" must be an array']
    return []
