"""The semantic tasks of `drafts-hybrid` — extraction and classification, never verdicts.

Each task asks the model for DATA (statements, verbs, levels) and the executors turn that
data into pass/fail deterministically (counts, order checks) — the extract-then-decide
half of the spectrum, the cheap half the abstention notes said to build first. The model
never chooses an outcome, so the judge's decision rule stays in reviewable code.

Everything here is identity (ADR-0034): the model each task pins, the sampling
parameters, the validation contracts. `SOURCE_CONFIG` carries the model ids, so changing
one without a VERSION bump is refused at ratification. Changing a model IS a version bump
by design — calibration does not transfer between judges.

Tasks are memoized per profile, for the length of one evaluation (`memo.py`): two criteria
deliberately read one extraction (the instrument writes them as separate criteria over the
same datum), profiles are immutable, and paying twice for one question would be pure waste.
"""

import json
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import Context, copy_context
from dataclasses import dataclass
from typing import Any

from app.modules.evaluation.domain.model import ProfileData, ProfileEntryData
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    grounding,
    prompts,
    runtime,
)
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.memo import TaskMemo
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
#
# Scoped to the evaluation, not to the process (`memo.py`): a task feeds several criteria
# and all of them must see the same answer — or the same failure, without re-asking a
# question that just degenerated (ADR-0037 §2) — while two evaluations must share nothing.

_memo = TaskMemo("drafts_hybrid_tasks")


cache_scope = _memo.scope


def clear_task_cache() -> None:
    _memo.clear()


def _memoized(
    task_id: str, profile: ProfileData, run: Callable[[], tuple[Any, LlmUsage]]
) -> tuple[Any, LlmUsage]:
    remembered: tuple[Any, LlmUsage] = _memo.memoized(task_id, profile, run)
    return remembered


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
                # The lesson's own span, not the model's rendering of it: the validator
                # accepts a quote that drops a bullet or an emphasis marker, and what a
                # report shows has to be findable in the course (ADR-0009).
                statement=grounding.locate(body, str(item["statement"])) or "",
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
        elif grounding.locate(body, statement) is None:
            # The grounding rule: a citation that is not in the source is not evidence. Read
            # through `grounding` since v12 — this check used to be byte equality against the
            # body, which refused a statement quoted across a bullet or with the emphasis
            # dropped, and refusing THAT is a finding about markdown rather than about the
            # course. It was the single most retried task in the package.
            violations.append(
                f"{label}.statement is not a quote from the lesson — copy the sentence "
                f"character-for-character (got: {statement.strip()[:120]!r})"
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
        concepts = profile.entries["lesson_concept_coverage"]
        concepts_by_id = {
            str(record["lessonId"]): record.get("concepts") or [] for record in concepts.value
        }
        plan_lines = "\n".join(
            json.dumps(
                {
                    "lessonId": str(lesson["lessonId"]),
                    "title": lesson.get("title"),
                    "type": lesson.get("type"),
                    "concepts": concepts_by_id.get(str(lesson["lessonId"]), []),
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


# --- task: the concept map (v13) --------------------------------------------------------
#
# Where each concept the course declares is STATED, and what each lesson DOES with it. Two
# criteria read this one map, which is why it is one task: paying twice for one question is
# what `memo.py` exists to prevent.
#
# Everything about its shape was measured before it was written, in the calibration dumps that
# preceded it — `docs/RUNBOOK-calibrating.md` and the frozen field runs it points at. The three
# decisions worth restating here, because an editor of this file will be tempted by each of
# them:
#
# 1. **The model is asked only for local, observable acts.** Which appearance of a concept is
#    its INTRODUCTION is arithmetic over what comes back, done in `executors.py`. A model asked
#    to reason about order answers by salience.
# 2. **Two passes, not one.** Definitions over the whole course; usage one module at a time.
#    Asked the other way round each question gets measurably worse, and the reason is the same
#    both times: what is in view moves the model's threshold.
# 3. **The plan's concept-to-lesson assignment is never shown.** It is joined back on
#    afterwards. Showing it invites the model to agree with the generator's bookkeeping, and a
#    draft was found whose `X.0` lesson does the work its `X.1` lesson is planned to teach.

# This task does not share the extraction model above, and that is deliberate rather than
# accidental drift. The flash model does not hold this output contract: over three drafts it
# produced 3, 1 and 0 usable rows, dropping `lessonId` and answering positionally, renaming
# groups, splicing quotes with an ellipsis. The failure was the contract, not the reading,
# which is the failure a more capable model is supposed to make disappear — and did.
CONCEPT_MAP_MODEL = "openai/gpt-5.6-luna"

# The only task here that thinks, and it has to. This one holds a numbered concept set against
# a dozen lesson bodies, which is exactly the shape the cheaper model was answering by
# position; at medium effort the definitions pass drifts to 14–15 of 18 against readers where
# high scores 17 of 17. `effort` and `max_tokens` are alternatives, never both, so this is the
# whole declaration.
CONCEPT_MAP_REASONING = {"effort": "high"}

# Four times the other tasks' ceiling, for the reason that killed `drafts-hybrid:1`: a
# reasoning model bills its thinking as output tokens, so the thinking competes with the answer
# for this number and can take all of it. A run cut at the budget is not a cheap run, it is a
# criterion that failed to execute.
CONCEPT_MAP_MAX_OUTPUT_TOKENS = 32000

# A degeneration bound per group, not a claim about pedagogy: a free-length array in an output
# schema is what every runaway in this package's history came out of.
MAX_LESSONS_PER_GROUP = 6

# The groups, split by which pass offers them. A group a pass is not offered is one it cannot
# answer in, which is how the two passes stay independent.
DEFINES_GROUP = "defines"
USAGE_GROUPS = ("develops", "uses_as_known", "assessed", "mentions")

# Pictures out, diagrams out, everything else in. An illustration in this format carries its
# GENERATION PROMPT as alt text — three hundred characters describing a picture nobody wrote as
# prose, naming concepts of the course — so left in, it is a passage a model honestly quotes as
# a lesson dealing with earlier material when what it quotes is our own image request. A mermaid
# block goes because it is diagram source sitting mid-paragraph: asked to quote around one, the
# model read straight through it and the grounding check refused what came back. Code fences
# and worked examples stay: they are where a concept is most often put to work.
_IMAGE = re.compile(r"!\[.*?\]\([^)]*\)", re.S)
_DIAGRAM = re.compile(r"```mermaid\b.*?```", re.S | re.I)


# One request of the fan-out: what it is called in a dropped-row note, the lessons it is shown,
# the groups it may answer in, and its two prompts.
_MapCall = tuple[str, list[dict[str, Any]], tuple[str, ...], str, str]

# What one of them comes back with: its rows, its dropped-row notes, and what it spent.
_MapAnswer = tuple[list["ConceptAppearance"], list[str], LlmUsage]


@dataclass(frozen=True)
class ConceptAppearance:
    """One concept, met in one lesson, in one of the five groups, quoted verbatim."""

    concept_index: int
    concept: str
    group: str
    lesson_id: str
    lesson_position: int
    quote: str


@dataclass(frozen=True)
class ConceptMap:
    """What the two passes found, and what they had to throw away finding it.

    `dropped` is carried rather than swallowed: a row refused for an unknown lesson or an
    ungrounded quote costs a criterion evidence it might have used, and a reader of the
    evaluation is entitled to know how much of the map never arrived.
    """

    appearances: tuple[ConceptAppearance, ...]
    concepts: int
    lessons: int
    calls: int
    dropped: tuple[str, ...]


def shown_body(body: str) -> str:
    """A lesson body as this task shows it: its own text, minus the pictures and diagrams."""
    return _IMAGE.sub("", _DIAGRAM.sub("", body))


def all_lessons(profile: ProfileData) -> list[dict[str, Any]]:
    """Every lesson in declared order, with the text shown — frame lessons included.

    They are in because they teach concepts too: hiding the lesson that states a concept and
    then asking where the concept is stated is asking for half an answer. Which lessons a
    criterion counts is the criterion's decision, made downstream.
    """
    ordered = ordered_inventory(profile)
    bodies = {
        str(lesson.get("lessonId")): str(lesson.get("body") or "")
        for lesson in profile.entries["lesson_bodies"].value
    }
    return [
        {
            "lessonId": str(lesson["lessonId"]),
            "title": lesson.get("title"),
            "position": position,
            "body": shown_body(bodies.get(str(lesson["lessonId"]), "")),
        }
        for position, lesson in enumerate(ordered)
    ]


def distinct_concepts(profile: ProfileData) -> list[str]:
    """One entry per distinct concept NAME, read off the plan and numbered.

    Read off `lesson_concept_coverage` rather than extracted, which costs no call and removes
    entity canonicalization entirely: the vocabulary is the generator's, so nothing has to
    decide whether two spellings are one concept. Names are merged because this format declares
    the same name in two different lessons five times over on one draft, and asking a model to
    choose between two identical labels is asking it to guess.
    """
    merged: dict[str, str] = {}
    for record in profile.entries["lesson_concept_coverage"].value:
        for concept in record.get("concepts") or []:
            text = str(concept).strip()
            if text:
                merged.setdefault(text.casefold(), text)
    return list(merged.values())


def modules_of(lessons: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """The lessons grouped by the module their identifier names, in delivery order.

    The unit of the usage fan-out. A module is two or three lessons rather than a dozen, which
    is the difference between a search over sixteen lessons — answered by finding the salient
    place and missing the diffuse ones — and a question about text the model holds at once.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for lesson in lessons:
        module = str(lesson["lessonId"]).split(".")[0]
        grouped.setdefault(module, []).append(lesson)
    return sorted(grouped.items())


def _corpus(concepts: list[str], lessons: list[dict[str, Any]]) -> str:
    """What one call is shown: the numbered concept names, then the lesson blocks."""
    numbered = "\n".join(f"[{index}] {name}" for index, name in enumerate(concepts))
    blocks = "\n\n".join(
        f"===== LESSON {lesson['lessonId']}: {lesson.get('title')} =====\n{lesson['body']}"
        for lesson in lessons
    )
    return f"CONCEPTS THE COURSE COVERS:\n{numbered}\n\nLESSONS:\n{blocks}"


def concept_map(profile: ProfileData) -> tuple[ConceptMap, LlmUsage]:
    """Where each declared concept is stated, and what each lesson does with it."""

    def run() -> tuple[ConceptMap, LlmUsage]:
        lessons = all_lessons(profile)
        concepts = distinct_concepts(profile)
        if not lessons or not concepts:
            empty = ConceptMap(
                appearances=(),
                concepts=len(concepts),
                lessons=len(lessons),
                calls=0,
                dropped=("the profile declares no lesson or no concept",),
            )
            return empty, LlmUsage(
                model=CONCEPT_MAP_MODEL, calls=0, tokens_in=0, tokens_out=0, latency_ms=0
            )

        calls: list[_MapCall] = [
            (
                "definitions",
                lessons,
                (DEFINES_GROUP,),
                prompts.CONCEPT_DEFINITIONS_SYSTEM,
                prompts.CONCEPT_DEFINITIONS_USER.substitute(
                    max_lessons=MAX_LESSONS_PER_GROUP, corpus=_corpus(concepts, lessons)
                ),
            ),
            *(
                (
                    f"module {name} usage",
                    shown,
                    USAGE_GROUPS,
                    prompts.CONCEPT_USAGE_SYSTEM,
                    prompts.CONCEPT_USAGE_USER.substitute(
                        max_lessons=MAX_LESSONS_PER_GROUP, corpus=_corpus(concepts, shown)
                    ),
                )
                for name, shown in modules_of(lessons)
            ),
        ]

        def ask(call: _MapCall) -> tuple[list[ConceptAppearance], list[str], LlmUsage]:
            name, shown, groups, system_prompt, user_prompt = call
            payload, usage = request_structured_output(
                runtime.get_client(),
                task_id="concept_map",
                model=CONCEPT_MAP_MODEL,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                validate=lambda answer: _validate_concept_map(answer, len(concepts), groups),
                temperature=TEMPERATURE,
                max_tokens=CONCEPT_MAP_MAX_OUTPUT_TOKENS,
                reasoning=CONCEPT_MAP_REASONING,
            )
            found, refused = _appearances_from(payload, shown, concepts, groups)
            return found, [f"{name}: {note}" for note in refused], usage

        # The calls are independent — the definitions pass and each module's usage pass share
        # no state and are never told about each other — so they go out together. On one draft
        # this stage was 84 % of an evaluation's wall clock at 517 seconds over seven serial
        # calls whose slowest was 114, which is the difference between a criterion you can run
        # over a dataset and one you cannot.
        #
        # No cap is set here on purpose. The transport holds one bounded semaphore per process
        # (`platform/llm.py`), and it exists precisely so that stacked fan-outs cannot burst
        # past `LLM_MAX_CONCURRENCY` — a second cap at this level would not compose with the
        # batch runner's, and nobody would have decided the product of the two.
        #
        # Nothing about the ANSWERS changes: each call is the same question with the same
        # corpus and the same sampling, and results are assembled BY CALL ORDER rather than by
        # completion, so two runs of one profile differ no more than they did serially
        # (ADR-0034: when an answer arrives is transport, which answer arrives is identity).
        #
        # Each worker runs inside a COPY of this context, and the copy is what makes the calls
        # observable: the trace sink is a `ContextVar` (`platform/observability.py`), a fresh
        # thread starts with an empty context, and without this the whole fan-out emitted
        # nothing — an evaluation whose most expensive task left no trace, which is the one
        # thing the calibration runbook cannot work without. One copy per call rather than one
        # shared: a `Context` cannot be entered from two threads at once.
        def ask_in_context(carried: tuple[Context, _MapCall]) -> _MapAnswer:
            context, call = carried
            return context.run(ask, call)

        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            answered = list(pool.map(ask_in_context, [(copy_context(), call) for call in calls]))

        appearances: list[ConceptAppearance] = []
        dropped: list[str] = []
        spend: list[LlmUsage] = []
        for found, refused, usage in answered:
            appearances.extend(found)
            dropped.extend(refused)
            spend.append(usage)

        found_map = ConceptMap(
            appearances=tuple(appearances),
            concepts=len(concepts),
            lessons=len(lessons),
            calls=len(calls),
            dropped=tuple(dropped),
        )
        return found_map, _sum_usage(spend)

    result, usage = _memoized("concept_map", profile, run)
    assert isinstance(result, ConceptMap)
    return result, usage


def _sum_usage(spend: list[LlmUsage]) -> LlmUsage:
    """What the whole fan-out spent, so the cost of one map stays readable in the report."""
    return LlmUsage(
        model=spend[0].model,
        calls=sum(one.calls for one in spend),
        tokens_in=sum(one.tokens_in for one in spend),
        tokens_out=sum(one.tokens_out for one in spend),
        latency_ms=sum(one.latency_ms for one in spend),
        clean_retries=sum(one.clean_retries for one in spend),
    )


def _appearances_from(
    payload: Any,
    lessons: list[dict[str, Any]],
    concepts: list[str],
    groups: tuple[str, ...],
) -> tuple[list[ConceptAppearance], list[str]]:
    """One answer turned into rows, saying out loud what it had to throw away.

    A call may only name the lessons it was shown; a row naming any other lesson is dropped
    rather than trusted, which is what keeps the usage fan-out honest about its own module.
    """
    by_id = {str(lesson["lessonId"]): lesson for lesson in lessons}
    found: list[ConceptAppearance] = []
    dropped: list[str] = []
    answered: set[int] = set()
    for entry in payload["concepts"]:
        index = _as_index(entry.get("conceptIndex")) if isinstance(entry, dict) else None
        if index is None or not 0 <= index < len(concepts) or index in answered:
            shown = entry.get("conceptIndex") if isinstance(entry, dict) else entry
            dropped.append(f"an entry for concept {shown!r}")
            continue
        answered.add(index)
        for group in groups:
            seen: set[str] = set()
            for appearance in entry.get(group) or []:
                if not isinstance(appearance, dict):
                    dropped.append(f"concept {index} {group}: an entry that is not an object")
                    continue
                lesson_id = str(appearance.get("lessonId"))
                if lesson_id not in by_id or lesson_id in seen:
                    dropped.append(f"concept {index} {group}: lesson {lesson_id!r}")
                    continue
                seen.add(lesson_id)
                body = str(by_id[lesson_id]["body"])
                quote = appearance.get("quote")
                if not isinstance(quote, str) or not quote.strip():
                    dropped.append(f"concept {index} {group} in {lesson_id}: no quote")
                    continue
                # The lesson's own span, never the model's rendering of it: what a report
                # shows has to be findable in the course (ADR-0009).
                span = grounding.locate(body, quote)
                if span is None:
                    dropped.append(
                        f"concept {index} {group} in {lesson_id}: quote not in that lesson"
                    )
                    continue
                found.append(
                    ConceptAppearance(
                        concept_index=index,
                        concept=concepts[index],
                        group=group,
                        lesson_id=lesson_id,
                        lesson_position=int(by_id[lesson_id]["position"]),
                        quote=span,
                    )
                )
    return found, dropped


def _validate_concept_map(answer: Any, concept_count: int, groups: tuple[str, ...]) -> list[str]:
    """Refuse only what makes the answer unreadable; everything else costs one row.

    The asymmetry is field-proven. A group name outside the ones offered is the model answering
    a different question and no reader can repair it, while a missing quote, an unknown lesson
    or a duplicate is one row lost out of dozens — and spending the retry budget on those is
    how a run comes back flattened instead of fixed.
    """
    if not isinstance(answer, dict):
        return ['the answer must be a JSON object with a "concepts" array']
    if not isinstance(answer.get("concepts"), list):
        return ['"concepts" must be an array']
    violations: list[str] = []
    for position, entry in enumerate(answer["concepts"]):
        label = f"concepts[{position}]"
        if not isinstance(entry, dict):
            violations.append(f"{label} must be an object")
            continue
        if _as_index(entry.get("conceptIndex")) is None:
            violations.append(f"{label}.conceptIndex must be a number from the list shown")
        unknown = [key for key in entry if key not in ("conceptIndex", *groups)]
        if unknown:
            violations.append(
                f"{label} carries {unknown[0]!r}, which is not one of the groups asked for: "
                f"{', '.join(groups)}"
            )
        for group in groups:
            value = entry.get(group)
            if value is None:
                continue
            if not isinstance(value, list):
                violations.append(f"{label}.{group} must be an array (use [] when empty)")
            elif len(value) > MAX_LESSONS_PER_GROUP:
                violations.append(
                    f"{label}.{group} holds {len(value)} lessons; list at most "
                    f"{MAX_LESSONS_PER_GROUP}"
                )
    return violations


def _as_index(value: Any) -> int | None:
    """The integer a model meant by an index, or `None` when it did not mean one.

    `"0"` is accepted because it is the same answer in a different serialization, and field
    runs met upstreams that quote their integers. A boolean is not an index, and neither is
    `"1.0"`. Deliberately a twin of the judging side's helper rather than an import: `judgments`
    reads this module, and identity here is duplicated on purpose (ADR-0034 §5).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


# --- shared shape check -----------------------------------------------------------------


def _shape_violations(answer: Any, key: str) -> list[str]:
    if not isinstance(answer, dict):
        return [f'the answer must be a JSON object with a "{key}" array']
    if not isinstance(answer.get(key), list):
        return [f'"{key}" must be an array']
    return []
