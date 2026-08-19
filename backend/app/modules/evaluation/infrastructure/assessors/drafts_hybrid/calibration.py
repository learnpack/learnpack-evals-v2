"""A calibration dump: what each lesson does with the concepts the course declares.

**This is not identity (ADR-0034), and nothing here decides an outcome.** No executor
imports this module, `SOURCE_CONFIG` does not name it, its prompts stay out of
`prompts._ALL_TEMPLATES` — the dict the ratification drift-guard fingerprints — and no
criterion is answered from what it produces. Editing this file is not a version of
`drafts-hybrid`. It exists to decide what three criteria should ASK, before any of them is
written, and a test pins that separation so it cannot drift into the judging path.

The three are `cr-later-lessons-apply-earlier-concepts`, `cr-concepts-introduced-before-use`
and `cr-adjacent-pair-has-a-bridge`. An earlier attempt implemented and measured them, and
the measurement was that two never fail and one always does — not a cost problem and not a
representation problem, but three defects in what was being asked:

1. **A backward reference is measured by nobody.** The reuse criterion excludes it in as
   many words ("judged elsewhere") and sends it to the bridge criterion, which sees only
   adjacent pairs and only the ends of each. An opening that says "this is a behavioral
   version of the change-pain heuristic from earlier lessons" falls between the two.
2. **The reuse criterion asked for a comparison the model could not make** — work "the
   lesson which teaches it did not already do" — while the corpus excluded the frame
   lessons, so for every concept taught in the opening the other term was not in view.
3. **One prompt written for one criterion was read by two.** Its whole framing looked
   backward and it capped touches at three "clearest", while the premature-use criterion
   needs a FORWARD use, which is rare and was never asked for.

So this dump is deliberately WIDER than any criterion and carries no threshold:

- every lesson is shown, frame ones included and marked, so the lesson that teaches a
  concept is always in view (defect 2);
- concepts declared LATER than the lesson touching them are wanted just as much, and which
  direction a touch runs is computed here, from the plan (defect 3);
- the semantic call is split into two independent axes, `mode` and `newness`, because the
  single `applied` fused them and a fused answer cannot be re-cut without paying for
  another run;
- each row carries the ZONE of its quote (opening / middle / closing, from the offset) and
  the DISTANCE in lessons, which is what says whether an adjacent-pair frame with a window
  at each end could ever catch the references a course actually has (defect 1);
- nothing is voted on, nothing is counted, and no pass condition is consulted.

What is kept from the earlier attempt is what three field runs paid for: the numbered
closed concept set read off the plan rather than extracted, `shown_body`, naming per block
the concept numbers a lesson may not report, and answering per unit inside one call.
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from string import Template
from typing import Any

from app.modules.evaluation.domain.model import ProfileData
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    grounding,
    runtime,
    tasks,
)
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.judgments import as_index
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.structured_output import (
    LlmUsage,
    request_structured_output,
)

# The data this dump cannot run without. Named here so the caller can refuse with a cause
# instead of raising a KeyError halfway through building a corpus.
REQUIRED_DATA = ("lesson_bodies", "lesson_inventory", "lesson_concept_coverage")

# Under test, and only here: the judging tasks stay on the flash model. The first field
# runs failed at the OUTPUT CONTRACT rather than at the reading — `lessonId` dropped and the
# entries answered positionally, `mode` renamed to `type`, quotes spliced with an ellipsis —
# which is the failure a more capable model is supposed to make disappear. Reasoning is on
# at `high` for the same reason: this task holds a numbered concept set against a dozen
# lesson bodies, which is the shape the flash model was answering by position.
MODEL = "openai/gpt-5.6-luna"

# This model does not take a temperature. It is still sent, because the transport owns that
# field and OpenRouter drops a parameter an upstream does not support rather than refusing
# the request; if that ever stops being true the transport is where it gets fixed, not here.
TEMPERATURE = 0.0

# `effort` and `max_tokens` are alternatives, never both (OpenRouter's reasoning guide), and
# `enabled` is redundant once `effort` is set — so this is the whole declaration.
REASONING = {"effort": "high"}

# One entry per lesson, each nesting up to `MAX_TOUCHES` quoted touches, so the answer grows
# as lessons x touches. Eight is above anything a lesson has legitimately shown; the cap
# exists because a free-length array in an output schema is what every degeneration in this
# package's history came out of, not to enforce parsimony.
#
# The budget is four times what the flash model needed, and the reason is the failure that
# killed `drafts-hybrid:1`: a reasoning model bills its thinking as output tokens, so the
# thinking competes with the answer for this number and can take all of it. At `high` effort
# over a dozen lesson bodies that is a real risk, and a run cut at the budget teaches
# nothing about whether the model can hold the contract.
MAX_OUTPUT_TOKENS = 32000
MAX_TOUCHES = 8

# What a lesson does with a concept another lesson declares. Two axes rather than one: the
# earlier attempt's `applied` meant "uses it AND does something new with it", so a reader
# who disagreed with where that line sat had no way to move it without buying another run.
# Split, the same answer supports every bar anyone might write.
MODES = ("uses_as_known", "re_explains", "points_at")
NEWNESS = ("new_context", "same_as_taught", "n_a")

# Where in its lesson a quote sits. The cut is 1200 characters at each end because that is
# the window an adjacent-pair bridge task reads, so "how many backward references sit
# outside the opening" is answerable against the design that would have to catch them.
ZONE_WINDOW_CHARS = 1200
ZONE_OPENING = "opening"
ZONE_MIDDLE = "middle"
ZONE_CLOSING = "closing"

# Where a concept sits relative to the lesson touching it, by the plan's delivery order.
DIRECTION_EARLIER = "earlier"
DIRECTION_LATER = "later"
DIRECTION_OWN = "own"

_IMAGE = re.compile(r"!\[.*?\]\([^)]*\)", re.S)
_DIAGRAM = re.compile(r"```mermaid\b.*?```", re.S | re.I)


CONCEPT_TOUCHES_SYSTEM = """\
You analyse how the lessons of a course refer to one another. Answer with a single JSON
object and nothing else — no prose, no markdown fences. Every value described as verbatim
must be copied character-for-character from the source text."""

CONCEPT_TOUCHES_USER = Template(
    """\
Below, between <lessons> tags, is the list of concepts a course declares — each with its
number in brackets and the lesson that teaches it — followed by the lessons themselves. A
lesson block starts at a line of the form "===== LESSON <id>: <title> =====", names the
concepts that lesson teaches itself, and runs until the next block.

For EACH lesson, report every concept FROM ANOTHER LESSON that the lesson deals with, and
what it does with each one. A lesson that deals with none reports an empty list.

Report ALL of them, not only the clearest. A concept counts whether the lesson that teaches
it comes BEFORE or AFTER this one: a lesson working with material the course only teaches
later is exactly as reportable as one working with material it already taught, and both are
wanted here.

Do not report the concepts a lesson teaches itself — its own block names those numbers.

Answer for the lessons shown here and no others, one entry each, even when the entry is
empty.

For every concept you report, QUOTE FIRST. Copy, verbatim, the passage of that lesson which
shows the lesson dealing with the concept — exactly as the lesson writes it, as one
continuous passage, never joining separate places together. Quote before you classify: the
passage is what the two answers below are about, and a touch you cannot quote is one you
must simply not report.

Then answer TWO independent questions about the passage you quoted.

First, "mode" — what the lesson does with it:

- "uses_as_known": the lesson treats the concept as available and operates with it — an
  example, an exercise, a walkthrough or an explanation that USES it without teaching it.
- "re_explains": the lesson explains, defines or summarises the concept again.
- "points_at": the lesson only points at it ("as we saw in lesson 01.2", "this builds on
  what you already know about X"), without using or re-explaining it.

Second, "newness" — how the work compares with the lesson that teaches the concept, which is
shown to you in this same corpus:

- "new_context": the lesson does something with the concept that the teaching lesson did
  not do — a different example, a different problem, a different application.
- "same_as_taught": the same work again — the teaching lesson's example, explanation or
  exercise repeated with little or no change.
- "n_a": there is no work to compare, which is the ordinary answer for "points_at".

The two are independent: answer each on its own terms, and do not let one decide the other.

This is an extraction task, not a judgement: report what each lesson does. Nothing here
asks whether the course is good, and no answer of yours decides anything about it.

Answer with this JSON shape, one entry per lesson, in this field order — the top-level key
is "lessons", and every touch carries all four fields:
{"lessons": [{"lessonId": "<the lesson's id>",
"touches": [{"conceptIndex": <a number from the concept list>,
"quote": "<verbatim passage from this lesson>",
"mode": "uses_as_known" | "re_explains" | "points_at",
"newness": "new_context" | "same_as_taught" | "n_a"}]}]}

At most $max_touches entries in "touches". Exactly one entry per lesson.

<lessons>
$corpus
</lessons>"""
)


@dataclass(frozen=True)
class ConceptTouchRow:
    """One place one lesson deals with one concept another lesson declares.

    Everything the model answered is `quote`, `mode` and `newness`, in that order — the
    quote first because a touch that cannot be cited is not one to report, and because a
    field written after two classifications is the field a model drops. Everything
    else on this row is computed here — where the concept is taught, which way the touch
    runs, how far, and where in the lesson the passage sits — because those are facts of
    the plan and of the text, and an answer that carried them would be free to move a
    concept in time.
    """

    lesson_id: str
    lesson_position: int
    is_frame: bool
    concept_index: int
    concept: str
    taught_in: str
    taught_position: int | None
    direction: str
    distance: int | None
    mode: str
    newness: str
    zone: str
    offset: int
    quote: str


@dataclass(frozen=True)
class DumpSummary:
    """What one dump covered, so a reader knows what the absence of rows means."""

    lessons: int
    frame_lessons: int
    concepts: int
    rows: int
    dropped: tuple[str, ...]


def shown_body(body: str) -> str:
    """A lesson body as this dump shows it: its own text, minus the pictures.

    An illustration in this format carries its GENERATION PROMPT as alt text — three hundred
    characters describing a picture nobody wrote as prose. One of them reads "cards labeled
    task, audience, goal, and limitation", naming four concepts of the course's first
    module: left in, it is a passage a model can honestly quote as a later lesson dealing
    with earlier material, when what it actually quotes is our own image request.

    A mermaid block goes for a second reason, found in the field. It is diagram SOURCE, not
    a sentence anyone reads, and it sits in the middle of a paragraph: asked to quote around
    one, the model read straight through and returned text from both sides of a diagram it
    silently skipped, which the grounding check refused and the retry repeated.

    Nothing else is removed. Code fences and worked examples are where a concept is most
    often put to work rather than restated, and this dump exists to see that.
    """
    return _IMAGE.sub("", _DIAGRAM.sub("", body))


def all_lessons(profile: ProfileData) -> list[dict[str, Any]]:
    """Every lesson in declared order, with the text shown, marking the frame ones.

    The frame lessons — first and last by declared position — are IN the corpus, unlike the
    earlier attempt's `ordered[1:-1]`. They teach concepts too, and asking a model how a
    lesson's work compares with the lesson that teaches the concept while hiding that lesson
    is asking for the half of a comparison. They are marked so a reader can exclude them
    afterwards, which is a decision the criteria get to make and this dump does not.
    """
    ordered = tasks.ordered_inventory(profile)
    bodies = {
        str(lesson.get("lessonId")): str(lesson.get("body") or "")
        for lesson in profile.entries["lesson_bodies"].value
    }
    last = len(ordered) - 1
    return [
        {
            "lessonId": str(lesson["lessonId"]),
            "title": lesson.get("title"),
            "position": position,
            "isFrame": position in (0, last),
            "body": shown_body(bodies.get(str(lesson["lessonId"]), "")),
        }
        for position, lesson in enumerate(ordered)
    ]


def declared_concepts(profile: ProfileData) -> list[dict[str, Any]]:
    """The course's own concept map, flattened and numbered, each keeping its lesson.

    Read off `lesson_concept_coverage` — what the generator says each lesson covers — rather
    than extracted from the bodies. It costs no call, it is the datum
    `cr-cognitive-demand-rises-across-the-course` already trusts, and it turns the expensive
    half of these questions ("what had the course taught by the time this lesson runs?")
    into a closed set the model matches against instead of an association it has to infer
    over the whole corpus. It also removes entity canonicalization entirely: the vocabulary
    is the generator's, so nothing has to decide whether two spellings are one concept.
    """
    numbered: list[dict[str, Any]] = []
    for record in profile.entries["lesson_concept_coverage"].value:
        lesson_id = str(record.get("lessonId"))
        for concept in record.get("concepts") or []:
            text = str(concept).strip()
            if text:
                numbered.append({"lessonId": lesson_id, "concept": text})
    return numbered


def own_concepts(
    lessons: Sequence[Mapping[str, Any]], concepts: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[int, ...]]:
    """Per lesson, the concept numbers the course declares that lesson itself teaches.

    Shown in the lesson's own block so the prompt can say "not these". Asked simply which
    numbered concepts a lesson works with, a model answers with the lesson's own — true,
    salient and useless to every question here. Naming the two or three numbers a lesson may
    NOT report is that instruction at a size a model holds; enumerating the twenty-odd it
    MAY report is the same instruction at a size that made both drafts die.
    """
    return {
        str(lesson["lessonId"]): tuple(
            index
            for index, concept in enumerate(concepts)
            if str(concept["lessonId"]) == str(lesson["lessonId"])
        )
        for lesson in lessons
    }


def concept_lines(concepts: Sequence[Mapping[str, Any]]) -> str:
    """One numbered line per declared concept, naming where the course teaches it."""
    return "\n".join(
        f"[{index}] taught in lesson {concept['lessonId']}: {concept['concept']}"
        for index, concept in enumerate(concepts)
    )


def lesson_blocks(lessons: Sequence[Mapping[str, Any]], own: Mapping[str, Sequence[int]]) -> str:
    """One block per lesson: its id, the concepts it teaches itself, and its body verbatim.

    Plain labelled blocks, never serialized — a lesson body is markdown full of quotes,
    braces and backslashes, and this task asks for verbatim passages out of it.
    """
    return "\n\n".join(
        f"===== LESSON {lesson['lessonId']}: {lesson.get('title')} =====\n"
        f"(this lesson teaches concept "
        f"{', '.join(str(index) for index in own[str(lesson['lessonId'])]) or 'none'} "
        f"— do not report those)\n"
        f"{lesson['body']}"
        for lesson in lessons
    )


def zone_of(offset: int, body_length: int) -> str:
    """Where in its lesson a passage sits, by the bridge window's own measure.

    A lesson shorter than one window is entirely `opening`, and that is the honest answer
    rather than a special case: a head window over such a body shows all of it, so every
    passage in it is one an adjacent-pair task would have been given.
    """
    if offset < ZONE_WINDOW_CHARS:
        return ZONE_OPENING
    if offset >= max(body_length - ZONE_WINDOW_CHARS, 0):
        return ZONE_CLOSING
    return ZONE_MIDDLE


def direction_of(taught_position: int | None, lesson_position: int) -> tuple[str, int | None]:
    """Which way a touch runs and how far, in lessons of the declared order."""
    if taught_position is None:
        return DIRECTION_OWN, None
    if taught_position < lesson_position:
        return DIRECTION_EARLIER, lesson_position - taught_position
    if taught_position > lesson_position:
        return DIRECTION_LATER, taught_position - lesson_position
    return DIRECTION_OWN, 0


def dump_concept_touches(
    profile: ProfileData,
) -> tuple[list[ConceptTouchRow], DumpSummary, LlmUsage]:
    """One call, one row per touch, no verdict anywhere.

    A row is DROPPED rather than the answer refused whenever the loss is one row: a quote
    that will not ground, a lesson nobody asked about, a duplicate. The earlier attempt
    learned that asymmetry the expensive way — a per-lesson array is a dozen chances to slip
    and a validator that refuses the whole answer turns any one of them into a dead run. In
    a dump a missing row costs a reader one line; a dead run costs the corpus.
    """
    lessons = all_lessons(profile)
    concepts = declared_concepts(profile)
    frame_count = sum(1 for lesson in lessons if lesson["isFrame"])
    if not lessons or not concepts:
        summary = DumpSummary(
            lessons=len(lessons),
            frame_lessons=frame_count,
            concepts=len(concepts),
            rows=0,
            dropped=("nothing to ask about: the profile declares no lesson or no concept",),
        )
        return [], summary, LlmUsage(model=MODEL, calls=0, tokens_in=0, tokens_out=0, latency_ms=0)

    lesson_ids = [str(lesson["lessonId"]) for lesson in lessons]
    own = own_concepts(lessons, concepts)
    corpus = (
        f"CONCEPTS THE COURSE DECLARES:\n{concept_lines(concepts)}\n\n"
        f"LESSONS:\n{lesson_blocks(lessons, own)}"
    )
    payload, usage = request_structured_output(
        runtime.get_client(),
        task_id="concept_touches_dump",
        model=MODEL,
        system_prompt=CONCEPT_TOUCHES_SYSTEM,
        user_prompt=CONCEPT_TOUCHES_USER.substitute(corpus=corpus, max_touches=MAX_TOUCHES),
        validate=lambda answer: validate_touches(answer, len(concepts)),
        temperature=TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
        reasoning=REASONING,
    )
    rows, dropped = _rows_from(payload, lessons, lesson_ids, concepts)
    summary = DumpSummary(
        lessons=len(lessons),
        frame_lessons=frame_count,
        concepts=len(concepts),
        rows=len(rows),
        dropped=tuple(dropped),
    )
    return rows, summary, usage


def _rows_from(
    payload: Any,
    lessons: Sequence[Mapping[str, Any]],
    lesson_ids: Sequence[str],
    concepts: Sequence[Mapping[str, Any]],
) -> tuple[list[ConceptTouchRow], list[str]]:
    """The answer turned into rows, saying out loud what it had to throw away.

    `dropped` is reported rather than swallowed: a dump whose silence could mean either "the
    course does not do this" or "the answer was unusable there" is not evidence about the
    course.
    """
    by_lesson = {str(lesson["lessonId"]): lesson for lesson in lessons}
    positions = {str(lesson["lessonId"]): int(lesson["position"]) for lesson in lessons}
    taught_at = {
        index: positions.get(str(concept["lessonId"])) for index, concept in enumerate(concepts)
    }
    rows: list[ConceptTouchRow] = []
    dropped: list[str] = []
    answered: set[str] = set()
    for entry in payload["lessons"]:
        lesson_id = str(entry.get("lessonId"))
        if lesson_id not in by_lesson:
            dropped.append(f"an entry for {lesson_id!r}, which is not a lesson of this course")
            continue
        if lesson_id in answered:
            dropped.append(f"a second entry for lesson {lesson_id}")
            continue
        answered.add(lesson_id)
        lesson = by_lesson[lesson_id]
        body = str(lesson["body"])
        seen: set[int] = set()
        for touch in entry.get("touches") or []:
            index = as_index(touch.get("conceptIndex"))
            if index is None or not 0 <= index < len(concepts) or index in seen:
                dropped.append(
                    f"lesson {lesson_id}: a touch on concept {touch.get('conceptIndex')!r}"
                )
                continue
            seen.add(index)
            quote = touch.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                # Worth telling apart from the one below: a touch reported with NO quote is
                # the model saying it saw something it would not cite, which is a fact about
                # the extraction, while an unfindable quote is a fact about the citation.
                dropped.append(
                    f"lesson {lesson_id}: a touch on concept {index}, reported with no quote"
                )
                continue
            span = grounding.locate(body, quote)
            if span is None:
                dropped.append(
                    f"lesson {lesson_id}: a touch on concept {index}, "
                    f"whose quote is not in that lesson"
                )
                continue
            offset = body.find(span)
            taught_position = taught_at.get(index)
            direction, distance = direction_of(taught_position, positions[lesson_id])
            rows.append(
                ConceptTouchRow(
                    lesson_id=lesson_id,
                    lesson_position=positions[lesson_id],
                    is_frame=bool(lesson["isFrame"]),
                    concept_index=index,
                    concept=str(concepts[index]["concept"]),
                    taught_in=str(concepts[index]["lessonId"]),
                    taught_position=taught_position,
                    direction=direction,
                    distance=distance,
                    mode=str(touch["mode"]),
                    newness=str(touch["newness"]),
                    zone=zone_of(offset, len(body)),
                    offset=offset,
                    # The source's own span, never the model's rendering (ADR-0009).
                    quote=span,
                )
            )
    missing = [lesson_id for lesson_id in lesson_ids if lesson_id not in answered]
    if missing:
        dropped.append(f"no entry at all for lesson(s): {', '.join(missing)}")
    return rows, dropped


def validate_touches(answer: Any, concept_count: int) -> list[str]:
    """Refuse only what makes the answer unreadable; everything else is a dropped row.

    What is refused is the shape and the two closed vocabularies — a `mode` outside its
    three values is the model answering a different question, and no reader can repair it.
    An out-of-range index, a duplicate, a missing entry and an ungrounded quote are all
    survivable, and are reported by `_rows_from` instead, because refusing the whole answer
    over one of a hundred touches is how the earlier attempt lost two field runs.
    """
    if not isinstance(answer, dict):
        return ['the answer must be a JSON object with a "lessons" array']
    if not isinstance(answer.get("lessons"), list):
        return ['"lessons" must be an array']
    violations: list[str] = []
    for position, entry in enumerate(answer["lessons"]):
        label = f"lessons[{position}]"
        if not isinstance(entry, dict):
            violations.append(f"{label} must be an object")
            continue
        if not isinstance(entry.get("lessonId"), str):
            violations.append(f"{label}.lessonId must be the lesson's id, as a string")
        touches = entry.get("touches")
        if touches is None:
            continue
        if not isinstance(touches, list):
            violations.append(
                f"{label}.touches must be an array (use [] when the lesson deals with none)"
            )
            continue
        if len(touches) > MAX_TOUCHES:
            violations.append(
                f"{label}.touches holds {len(touches)} entries; report at most {MAX_TOUCHES}"
            )
        for at, touch in enumerate(touches):
            entry_label = f"{label}.touches[{at}]"
            if not isinstance(touch, dict):
                violations.append(f"{entry_label} must be an object")
                continue
            if touch.get("mode") not in MODES:
                violations.append(f"{entry_label}.mode must be one of: {', '.join(MODES)}")
            if touch.get("newness") not in NEWNESS:
                violations.append(f"{entry_label}.newness must be one of: {', '.join(NEWNESS)}")
            # A missing quote is NOT refused here, and the field taught that the hard way: a
            # provider that omits the field omits it on every attempt, so making it fatal
            # spent three rounds and killed the run over touches the model had genuinely
            # found. It costs its own row instead, reported like any other loss — same rule
            # as a quote that will not ground, which is the same defect one step later.
    return violations


# --- what a reader gets ------------------------------------------------------------------


_COLUMNS = (
    "lesson",
    "pos",
    "frame",
    "#",
    "concept",
    "taught in",
    "dir",
    "dist",
    "mode",
    "newness",
    "zone",
    "quote",
    "your call",
)


def render_markdown(
    rows: Sequence[ConceptTouchRow], summary: DumpSummary, title: str, usage: LlmUsage
) -> str:
    """The table a person marks up, with an empty column for their own call.

    The reader's column is the point of the whole exercise: `mode` and `newness` are what
    the model saw, `your call` is where the bar actually goes, and the two side by side are
    the only measurement of the distance between them that exists.
    """
    lines = [
        f"# Concept touches — {title}",
        "",
        f"{summary.lessons} lessons ({summary.frame_lessons} frame) · "
        f"{summary.concepts} declared concepts · {summary.rows} touches · "
        f"{usage.calls} call(s), {usage.tokens_in} in / {usage.tokens_out} out, "
        f"{usage.clean_retries} clean retries",
        "",
        "No verdict is computed here and no threshold is applied: `mode` and `newness` are "
        "what the model reported, and `your call` is empty on purpose.",
        "",
        "| " + " | ".join(_COLUMNS) + " |",
        "|" + "|".join("---" for _ in _COLUMNS) + "|",
    ]
    for row in sorted(rows, key=lambda r: (r.lesson_position, r.concept_index)):
        lines.append(
            "| "
            + " | ".join(
                (
                    row.lesson_id,
                    str(row.lesson_position),
                    "yes" if row.is_frame else "",
                    str(row.concept_index),
                    _cell(row.concept),
                    row.taught_in,
                    row.direction,
                    "" if row.distance is None else str(row.distance),
                    row.mode,
                    row.newness,
                    row.zone,
                    _cell(row.quote),
                    "",
                )
            )
            + " |"
        )
    if summary.dropped:
        lines.extend(["", "## What the answer did not yield", ""])
        lines.extend(f"- {note}" for note in summary.dropped)
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    """Table cells hold markdown, so a pipe or a newline in a quote would break the row."""
    return " ".join(text.split()).replace("|", "\\|")


def as_json(rows: Sequence[ConceptTouchRow], summary: DumpSummary, usage: LlmUsage) -> str:
    """The same rows unrendered, so a second reading needs no second call."""
    return json.dumps(
        {
            "summary": asdict(summary),
            "usage": asdict(usage),
            "rows": [asdict(row) for row in rows],
        },
        indent=2,
        ensure_ascii=False,
    )


# --- the concept-major dump ----------------------------------------------------------------
#
# The same corpus asked the other way round, and the reason is measured rather than aesthetic.
# The lesson-major dump above is unstable in two specific places, and both are properties of
# its SHAPE rather than of the question:
#
# - Its answer is a list of lessons each holding a variable-length list of touches, so two
#   runs at identical settings reported 40 touches and 29. Here the answer has exactly one
#   entry per concept, and how many concepts there are is a fact of the plan — the output
#   length is pinned, which is the move v12 made when it went from one verdict over four
#   objectives to one entry per objective.
# - Its `newness` axis asked how a passage compares with the lesson that TEACHES the concept,
#   a lesson the model had to go and find; between two runs of one model that answer inverted
#   wholesale (25 `same_as_taught` against 8). Here every appearance of one concept is decided
#   inside a single entry, so the comparison is in view by construction.
#
# And one thing it can do that the other cannot. The plan's concept-to-lesson assignment is
# NOT shown: the model gets bare concept names and is asked where the text defines and uses
# them. That un-entangles the answer from the generator's own bookkeeping, and it turns the
# session's worst confound into a measurement — a draft whose `04.0` does the work its plan
# assigns to `04.1` shows up as `defined_in` disagreeing with `declaredIn`, mechanically,
# instead of quietly suppressing another criterion's numerator.
#
# Duplicate names are merged before asking. Five pairs of this format's concepts share a name
# across lessons, and in the lesson-major dump that forced an arbitrary choice between two
# indices which then decided a touch's direction — 6 of 97 rows on one draft. One entry per
# distinct name dissolves that rather than resolving it by coin flip.

# Where a lesson sits for one concept. Each lesson goes in exactly ONE of these per concept:
# the group that best describes what it does. `explained_in`, `used_as_known_in` and
# `mentioned_in` are the lesson-major `re_explains`, `uses_as_known` and `points_at` under
# other names, so the two experiments stay comparable; `defined_in` and `assessed_in` are what
# this shape adds.
BUCKETS = ("defined_in", "explained_in", "used_as_known_in", "assessed_in", "mentioned_in")

# A degeneration bound per group, not a claim about pedagogy: a free-length array in an output
# schema is what every runaway in this package's history came out of. Six is above what any
# concept has legitimately shown over a sixteen-lesson draft.
MAX_LESSONS_PER_BUCKET = 6

CONCEPT_MAP_SYSTEM = """\
You analyse where the concepts of a course are taught and used. Answer with a single JSON
object and nothing else — no prose, no markdown fences. Every value described as verbatim
must be copied character-for-character from the source text."""

CONCEPT_MAP_USER = Template(
    """\
Below, between <course> tags, is a numbered list of the concepts a course covers, followed by
every lesson of that course. A lesson block starts at a line of the form
"===== LESSON <id>: <title> =====" and runs until the next block.

You are NOT told which lesson teaches which concept. Working that out from the text is part
of the task.

For EACH concept in the list, report the lessons that deal with it, sorting each lesson into
exactly ONE of these five groups — the one that best describes what that lesson does with
that concept:

- "defined_in": the lesson INTRODUCES the concept — it names it and says what it is, for a
  reader not assumed to know it yet.
- "explained_in": the lesson elaborates, restates or summarises the concept without
  introducing it.
- "used_as_known_in": the lesson OPERATES with the concept, treating the reader as already
  having it — an example, a walkthrough or an explanation that uses it without teaching it.
- "assessed_in": the lesson puts a task, question or exercise to the learner that checks
  whether they have the concept.
- "mentioned_in": the lesson names the concept without doing any of the above.

A lesson appears at most once per concept, in one group only. A concept no lesson deals with
reports five empty lists — do not force every concept to be found.

For every lesson you list, quote verbatim the passage of THAT lesson which shows it. Copy it
exactly as the lesson writes it, as one continuous passage — never join separate places
together. A lesson you cannot quote is one not to list.

This is an extraction task, not a judgement: report where the text puts each concept. Nothing
here asks whether the course is good, and no answer of yours decides anything about it.

Answer with this JSON shape, one entry per concept, all of them, in this field order:
{"concepts": [{"conceptIndex": <the number from the list>,
"defined_in":       [{"lessonId": "<id>", "quote": "<verbatim>"}],
"explained_in":     [{"lessonId": "<id>", "quote": "<verbatim>"}],
"used_as_known_in": [{"lessonId": "<id>", "quote": "<verbatim>"}],
"assessed_in":      [{"lessonId": "<id>", "quote": "<verbatim>"}],
"mentioned_in":     [{"lessonId": "<id>", "quote": "<verbatim>"}]}]}

At most $max_lessons lessons in any one group. Exactly one entry per concept.

<course>
$corpus
</course>"""
)


@dataclass(frozen=True)
class ConceptAppearanceRow:
    """One concept, met in one lesson, in one of the five groups.

    `declared_in` and `declared_here` are the PLAN's answer, joined here and never shown to
    the model — which is the whole point of this shape. Where a `defined_in` row's
    `declared_here` is false, the generator's plan and the generator's prose disagree about
    where a concept is taught, and that is a finding rather than noise.
    """

    concept_index: int
    concept: str
    bucket: str
    lesson_id: str
    lesson_position: int
    is_frame: bool
    declared_in: tuple[str, ...]
    declared_here: bool
    zone: str
    offset: int
    quote: str


@dataclass(frozen=True)
class MapSummary:
    """What one map covered, so a reader knows what the absence of a row means."""

    concepts: int
    lessons: int
    rows: int
    found: int
    dropped: tuple[str, ...]


def distinct_concepts(profile: ProfileData) -> list[dict[str, Any]]:
    """One entry per distinct concept NAME, keeping every lesson the plan declares it in.

    Merged rather than one entry per declaration: this format declares the same name in two
    different lessons five times over on one draft, and asking a model to choose between two
    identical labels is asking it to guess.
    """
    order = {str(lesson["lessonId"]): int(lesson["position"]) for lesson in all_lessons(profile)}
    merged: dict[str, dict[str, Any]] = {}
    for record in profile.entries["lesson_concept_coverage"].value:
        lesson_id = str(record.get("lessonId"))
        for concept in record.get("concepts") or []:
            text = str(concept).strip()
            if not text:
                continue
            slot = merged.setdefault(text.casefold(), {"concept": text, "declaredIn": []})
            if lesson_id not in slot["declaredIn"]:
                slot["declaredIn"].append(lesson_id)
    return [
        {
            "concept": slot["concept"],
            "declaredIn": tuple(slot["declaredIn"]),
            "declaredPositions": tuple(order[lid] for lid in slot["declaredIn"] if lid in order),
        }
        for slot in merged.values()
    ]


def bare_concept_lines(concepts: Sequence[Mapping[str, Any]]) -> str:
    """The concept list as the model sees it: numbers and names, and no lesson."""
    return "\n".join(f"[{index}] {c['concept']}" for index, c in enumerate(concepts))


def plain_lesson_blocks(lessons: Sequence[Mapping[str, Any]]) -> str:
    """One block per lesson, with nothing said about which concepts are its own."""
    return "\n\n".join(
        f"===== LESSON {lesson['lessonId']}: {lesson.get('title')} =====\n{lesson['body']}"
        for lesson in lessons
    )


def dump_concept_map(
    profile: ProfileData,
) -> tuple[list[ConceptAppearanceRow], MapSummary, LlmUsage]:
    """One call, one entry per concept, no verdict anywhere."""
    lessons = all_lessons(profile)
    concepts = distinct_concepts(profile)
    if not lessons or not concepts:
        summary = MapSummary(
            concepts=len(concepts),
            lessons=len(lessons),
            rows=0,
            found=0,
            dropped=("nothing to ask about: the profile declares no lesson or no concept",),
        )
        return [], summary, LlmUsage(model=MODEL, calls=0, tokens_in=0, tokens_out=0, latency_ms=0)

    corpus = (
        f"CONCEPTS THE COURSE COVERS:\n{bare_concept_lines(concepts)}\n\n"
        f"LESSONS:\n{plain_lesson_blocks(lessons)}"
    )
    payload, usage = request_structured_output(
        runtime.get_client(),
        task_id="concept_map_dump",
        model=MODEL,
        system_prompt=CONCEPT_MAP_SYSTEM,
        user_prompt=CONCEPT_MAP_USER.substitute(corpus=corpus, max_lessons=MAX_LESSONS_PER_BUCKET),
        validate=lambda answer: validate_concept_map(answer, len(concepts)),
        temperature=TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
        reasoning=REASONING,
    )
    rows, dropped = _map_rows_from(payload, lessons, concepts)
    summary = MapSummary(
        concepts=len(concepts),
        lessons=len(lessons),
        rows=len(rows),
        found=len({row.concept_index for row in rows}),
        dropped=tuple(dropped),
    )
    return rows, summary, usage


def _map_rows_from(
    payload: Any, lessons: Sequence[Mapping[str, Any]], concepts: Sequence[Mapping[str, Any]]
) -> tuple[list[ConceptAppearanceRow], list[str]]:
    """The answer turned into rows, saying out loud what it had to throw away."""
    by_id = {str(lesson["lessonId"]): lesson for lesson in lessons}
    rows: list[ConceptAppearanceRow] = []
    dropped: list[str] = []
    answered: set[int] = set()
    for entry in payload["concepts"]:
        index = as_index(entry.get("conceptIndex")) if isinstance(entry, dict) else None
        if index is None or not 0 <= index < len(concepts) or index in answered:
            shown = entry.get("conceptIndex") if isinstance(entry, dict) else entry
            dropped.append(f"an entry for concept {shown!r}")
            continue
        answered.add(index)
        info = concepts[index]
        for bucket in BUCKETS:
            seen: set[str] = set()
            for appearance in entry.get(bucket) or []:
                if not isinstance(appearance, dict):
                    dropped.append(f"concept {index} {bucket}: an entry that is not an object")
                    continue
                lesson_id = str(appearance.get("lessonId"))
                if lesson_id not in by_id or lesson_id in seen:
                    dropped.append(f"concept {index} {bucket}: lesson {lesson_id!r}")
                    continue
                seen.add(lesson_id)
                body = str(by_id[lesson_id]["body"])
                quote = appearance.get("quote")
                if not isinstance(quote, str) or not quote.strip():
                    dropped.append(f"concept {index} {bucket} in {lesson_id}: no quote")
                    continue
                span = grounding.locate(body, quote)
                if span is None:
                    dropped.append(
                        f"concept {index} {bucket} in {lesson_id}: quote not in that lesson"
                    )
                    continue
                offset = body.find(span)
                rows.append(
                    ConceptAppearanceRow(
                        concept_index=index,
                        concept=str(info["concept"]),
                        bucket=bucket,
                        lesson_id=lesson_id,
                        lesson_position=int(by_id[lesson_id]["position"]),
                        is_frame=bool(by_id[lesson_id]["isFrame"]),
                        declared_in=tuple(info["declaredIn"]),
                        declared_here=lesson_id in info["declaredIn"],
                        zone=zone_of(offset, len(body)),
                        offset=offset,
                        quote=span,
                    )
                )
    missing = [i for i in range(len(concepts)) if i not in answered]
    if missing:
        dropped.append(f"no entry at all for concept(s): {missing}")
    return rows, dropped


def validate_concept_map(answer: Any, concept_count: int) -> list[str]:
    """Refuse only what makes the answer unreadable; everything else is a dropped row.

    Same asymmetry the lesson-major dump learned in the field: a group name outside the five
    is the model answering a different question and no reader can repair it, while a missing
    quote, an unknown lesson and a duplicate cost one row each.
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
        if as_index(entry.get("conceptIndex")) is None:
            violations.append(f"{label}.conceptIndex must be a number from the list shown")
        unknown = [key for key in entry if key not in ("conceptIndex", *BUCKETS)]
        if unknown:
            violations.append(
                f"{label} carries {unknown[0]!r}, which is not one of the five groups: "
                f"{', '.join(BUCKETS)}"
            )
        for bucket in BUCKETS:
            value = entry.get(bucket)
            if value is None:
                continue
            if not isinstance(value, list):
                violations.append(f"{label}.{bucket} must be an array (use [] when empty)")
            elif len(value) > MAX_LESSONS_PER_BUCKET:
                violations.append(
                    f"{label}.{bucket} holds {len(value)} lessons; list at most "
                    f"{MAX_LESSONS_PER_BUCKET}"
                )
    return violations


_MAP_COLUMNS = (
    "#",
    "concept",
    "group",
    "lesson",
    "pos",
    "frame",
    "plan declares it in",
    "here?",
    "zone",
    "quote",
    "your call",
)


def render_map_markdown(
    rows: Sequence[ConceptAppearanceRow], summary: MapSummary, title: str, usage: LlmUsage
) -> str:
    """The table a person marks up, concept by concept."""
    lines = [
        f"# Concept map — {title}",
        "",
        f"{summary.concepts} distinct concepts ({summary.found} placed somewhere) · "
        f"{summary.lessons} lessons · {summary.rows} appearances · "
        f"{usage.calls} call(s), {usage.tokens_in} in / {usage.tokens_out} out, "
        f"{usage.clean_retries} clean retries",
        "",
        "The model was NOT told where the plan declares each concept: `plan declares it in` "
        "and `here?` are joined afterwards. A `defined_in` row whose `here?` is empty is the "
        "plan and the prose disagreeing about where a concept is taught.",
        "",
        "| " + " | ".join(_MAP_COLUMNS) + " |",
        "|" + "|".join("---" for _ in _MAP_COLUMNS) + "|",
    ]
    ordered = sorted(
        rows, key=lambda r: (r.concept_index, BUCKETS.index(r.bucket), r.lesson_position)
    )
    for row in ordered:
        lines.append(
            "| "
            + " | ".join(
                (
                    str(row.concept_index),
                    _cell(row.concept),
                    row.bucket,
                    row.lesson_id,
                    str(row.lesson_position),
                    "yes" if row.is_frame else "",
                    " ".join(row.declared_in),
                    "yes" if row.declared_here else "",
                    row.zone,
                    _cell(row.quote),
                    "",
                )
            )
            + " |"
        )
    if summary.dropped:
        lines.extend(["", "## What the answer did not yield", ""])
        lines.extend(f"- {note}" for note in summary.dropped)
    return "\n".join(lines) + "\n"


def map_as_json(rows: Sequence[ConceptAppearanceRow], summary: MapSummary, usage: LlmUsage) -> str:
    """The same rows unrendered, so a second reading needs no second call."""
    return json.dumps(
        {
            "summary": asdict(summary),
            "usage": asdict(usage),
            "rows": [asdict(row) for row in rows],
        },
        indent=2,
        ensure_ascii=False,
    )
