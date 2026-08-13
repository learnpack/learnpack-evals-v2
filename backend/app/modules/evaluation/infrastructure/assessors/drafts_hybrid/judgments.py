"""The judging tasks of `drafts-hybrid` — where the model decides, not just extracts.

`tasks.py` asks the model for DATA and lets code decide; this module is the other half of
ADR-0016's spectrum: criteria whose pass condition has no mechanical proxy ("does the
closing integrate what the course taught?") and where the verdict itself is the model's.
The decision rule does not disappear into the model — it is the instrument's
`pass_condition`, quoted verbatim into the prompt, which is exactly where a criterion's
normative content is supposed to live (ADR-0010).

Three rules keep this honest:

1. **The normative text is never copied here.** Every judge prompt is built from the
   `CriterionSpec` the executor already receives — its `pass_condition` and its declared
   `failure_modes`. There is one source of truth for what a criterion demands, and it is
   the published instrument. The consequence is worth stating out loud because it is new:
   bumping the INSTRUMENT changes what the judge asks without moving this package's
   `promptsFingerprint`. That is governed, not accidental — ratifying an assessor against
   a new instrument version is an explicit act (ADR-0019), and it is the act where someone
   confirms the criteria that changed.

2. **Every verdict is grounded.** The answer must quote a passage that is a verbatim
   substring of the text the prompt showed, checked by the validator like any other
   contract violation: fed back once, fatal when persistent. A verdict whose evidence
   cannot be found in the source is not evidence (ADR-0009), and the executors pass that
   quote straight into `ExecutorResult`, so what a report shows is what the judge read.

3. **The failure mode comes from the instrument's own list.** When the verdict is false the
   model names WHICH declared failure it saw, by number, validated to be in range. It
   cannot invent one: the vocabulary is the criterion's, and an out-of-range answer is a
   contract violation. This is what lets a judged `fail` say something more useful than
   "mode 0" without letting the judge write normative text.

Field order in every answer is `reason` -> `evidence` -> `verdict` -> `failureMode`, and
the shape shown to the model says so. JSON mode emits fields in the order the model writes
them, so a verdict-first shape would have it commit before working through its own
reasoning. Asking for the reason first buys the effect of thinking without paying for
reasoning tokens — which matters here because `REASONING` stays at `effort: "none"` and
the budget that killed v1 stays spent on answers.

Everything in this module is IDENTITY (ADR-0034): the models, the sampling, the retry
budget, the shape of the question and the grounding rule. Editing it is a new version of
`drafts-hybrid`.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.evaluation.domain.model import (
    CriterionSpec,
    ProfileData,
    ProfileEntryData,
)
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    prompts,
    runtime,
    tasks,
)
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.memo import TaskMemo
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid.structured_output import (
    LlmUsage,
    request_structured_output,
)
from app.modules.evaluation.infrastructure.assessors.errors import AssessorExecutionError

# One model for every judging task, pinned here (ADR-0034). Same model the extraction
# tasks use: the calibration of v2 showed it answers these shapes on the first attempt,
# and a second model id would be a second thing to re-calibrate when either moves.
JUDGE_MODEL = "deepseek/deepseek-v4-flash-0731"
ASSESSMENT_MAPPING_MODEL = "deepseek/deepseek-v4-flash-0731"
ASSESSMENT_REACH_MODEL = "deepseek/deepseek-v4-flash-0731"

# How many independent answers a judgement is decided by: ask two, and only pay for a third
# when they disagree. The verdict this yields is EXACTLY the one a always-three majority
# would give — two agreeing samples cannot be overturned by a third — at about 2.2 calls
# instead of 3.
#
# Sampling at all is not a hedge: repeats of the same question over the same text do
# disagree, because the variance outlives temperature 0 (it comes from how the server batches
# work, not from how the tokens are drawn). Correcting an ambiguous criterion removes far more
# disagreement than voting ever will — but only for the ambiguity someone has already found,
# and borderline instances surface one per draft, so there is no enumerable list of "hard
# criteria" to sample selectively.
#
# `MAX_SAMPLES` must stay strictly greater than `SAMPLES`, or a split would have nothing to
# break the tie with. Both are identity: how many answers decide a verdict decides which
# verdict survives, so moving either is a VERSION bump.
SAMPLES = 2
MAX_SAMPLES = 3

# How many passages one judgement may rest on. The list exists because a finding often rests
# on several places in the text, and asking for exactly one was what made a correct verdict
# get rejected — but unbounded, it is a way to spend the whole output budget: one calibration
# answer looped a nine-quote cycle twenty times, emitted 191 entries of which 18 were
# distinct, and stopped at `finish_reason: length` having consumed 8000 tokens, three
# quarters of that whole evaluation's output. With a vote, such an answer is paid for two or
# three times.
#
# 12 is chosen against the observed spread rather than by taste: across every judged answer
# so far the legitimate ones run 1 to 8 quotes, the 8 belonging to the criterion that reads
# one block per declared objective and therefore scales with the draft. The cap is there to
# stop degeneration, not to enforce parsimony.
MAX_EVIDENCE = 12

# What a judging call may emit. `MAX_EVIDENCE` bounds what a judgement may CONTAIN, and it
# is checked after the answer arrives — which stops garbage being stored but not from being
# paid for. Only the budget stops that, and 8000 (the figure the extraction tasks need,
# inherited from v2's reasoning problem) buys about three minutes of a model repeating one
# sentence into the evidence array. Judged answers that completed run a median of 153 output
# tokens and a maximum of 773 across every run so far, so 1500 is roughly twice the widest
# real answer and cuts a degeneration off in seconds instead of minutes.
#
JUDGE_MAX_OUTPUT_TOKENS = 1500

# The two extraction tasks here get a bound of their own. They were left on the shared 8000
# on the reasoning that only judging had ever degenerated — which the next run falsified:
# `assessment_reach` filled `referencesLessonIds` with repeated and then invented lesson ids
# until the budget was gone, 124 seconds for nothing. Degeneration is not a property of
# judging; it is what any FREE-LENGTH ARRAY in an output schema invites, and both of these
# have one.
#
# Their output does scale with the draft — one entry per objective, one per item — so the
# bound is set well above the measured maxima (424 tokens for the mapping, 518 for the reach)
# rather than close to them: roughly five times, which is a draft several times larger than
# any measured, and still cuts a loop off in a third of the time.
#
# `tasks.py`'s three extraction tasks keep the shared budget on purpose: none has degenerated,
# and `concept_trajectory` has legitimately spent 2412 tokens on a long plan.
EXTRACTION_MAX_OUTPUT_TOKENS = 2500


@dataclass(frozen=True)
class Verdict:
    """One judged criterion: what the judge decided, and the passages it decided it on.

    `evidence` is a LIST because a finding often rests on several places in the text — three
    objectives measured by the wrong kind of item is three pieces of evidence, not one. The
    first calibration runs proved the point the hard way: asked for a single quote, the
    model stitched six passages together with "..." and the grounding check rejected an
    answer whose judgement was correct, three times in a row, identically. The quote shape
    has to match the shape of the finding.
    """

    reason: str
    evidence: tuple[str, ...]
    passed: bool
    failure_mode_index: int | None


@dataclass(frozen=True)
class Judgement:
    """A criterion decided by a vote, and how close that vote was.

    `agreed` out of `samples` is not a footnote: a criterion answered 2-1 is one whose
    threshold the instrument never wrote down, and every such criterion found so far was
    found exactly this way — the model agreeing on the facts and dividing on whether they
    clear the bar. The split travels with the evaluation so that reading it is possible.
    """

    verdict: Verdict
    usage: LlmUsage
    agreed: int
    samples: int


@dataclass(frozen=True)
class ObjectiveMapping:
    """One declared objective and the assessment items that were found to measure it."""

    objective_id: str
    reason: str
    evidence: str
    item_indices: tuple[int, ...]


@dataclass(frozen=True)
class ItemReach:
    """One assessment item and the lessons it draws on."""

    index: int
    reason: str
    references: tuple[str, ...]


# --- memoization ------------------------------------------------------------------------
#
# Same rationale as `tasks.py`: profiles are immutable and the question is fixed, so two
# criteria reading one answer must not pay for it twice. Here it is the assessment mapping
# that two criteria share.

_memo = TaskMemo("drafts_hybrid_judgments")


cache_scope = _memo.scope


def clear_judgment_cache() -> None:
    _memo.clear()


def _memoized(task_id: str, profile: ProfileData, run: Callable[[], Any]) -> Any:
    """Whatever `run` returns, once per (task, profile) in this evaluation. Callers that
    also need the spend return it inside the value — a `Judgement` carries its own, the
    extraction tasks pair theirs with the data."""
    return _memo.memoized(task_id, profile, run)


# --- grounding: finding the model's quote in the source ----------------------------------


def locate(corpus: str, quote: str) -> str | None:
    """The corpus's OWN span matching `quote` up to whitespace, or `None` if it is not there.

    Two decisions, both learnt from calibration runs that failed on quotes whose judgement
    was fine:

    - **Whitespace is not content.** A corpus built by this module puts items on their own
      indented lines, and a model that quotes across one renders the newline and indent as a
      single space. Comparing byte for byte rejected that, which is a false negative about
      the course. Runs of whitespace are equal to each other for the purpose of finding the
      passage.
    - **Neither is markdown emphasis.** Lesson bodies are markdown, so a sentence can carry
      `**bold**` or backticks, and a model quoting it drops them about as often as it keeps
      them. Same class of false negative, same answer: the markers are invisible to the match.
    - **What is returned is the SOURCE's text, never the model's.** Tolerating a difference
      when matching is not the same as storing the difference: the quote that ends up in a
      report is the span as the course writes it — emphasis markers included — so ADR-0009
      stays exact.
    """
    flat_corpus, offsets = _flatten(corpus)
    flat_quote, _ = _flatten(quote)
    if not flat_quote:
        return None
    at = flat_corpus.find(flat_quote)
    if at < 0:
        return None
    return corpus[offsets[at] : offsets[at + len(flat_quote) - 1] + 1]


# Markdown emphasis, dropped when matching a quote against its source. Skipping `_` is the
# one that can bite in the other direction: it makes `lesson_bodies` and `lessonbodies` equal
# for the search. Accepted — it is a false positive in the direction we already chose to
# tolerate, and reaching it needs the model to delete an underscore, which is a formatting
# edit rather than an invention.
_EMPHASIS = frozenset("*_`")


def _flatten(text: str) -> tuple[str, list[int]]:
    """`text` with whitespace runs collapsed to one space, emphasis markers dropped and the
    ends stripped, plus, per character kept, the index it came from — which is what lets a
    match map back to the original."""
    kept: list[str] = []
    offsets: list[int] = []
    after_space = True
    for index, char in enumerate(text):
        if char in _EMPHASIS:
            # Not `continue`-ing through the space branch on purpose: an emphasis marker is
            # invisible, so `**a** **b**` still flattens to `a b` rather than `ab`.
            continue
        if char.isspace():
            if not after_space:
                kept.append(" ")
                offsets.append(index)
                after_space = True
            continue
        kept.append(char)
        offsets.append(index)
        after_space = False
    if kept and kept[-1] == " ":
        kept.pop()
        offsets.pop()
    return "".join(kept), offsets


def _grounding_violations(label: str, quote: str, corpus: str) -> list[str]:
    """Why this quote is not evidence — naming the RULE that was broken, not just the fact.

    The generic "not verbatim" message cost a whole evaluation: the model had joined real
    passages with "..." and, told only that its quote was not verbatim, answered the same
    thing three times, because from where it stood every fragment WAS copied. Feedback has
    to name what to do differently.
    """
    if locate(corpus, quote) is not None:
        return []
    if "..." in quote or "…" in quote:
        return [
            f"{label} joins separate passages with an ellipsis. Each entry of "
            '"evidence" must be ONE CONTINUOUS passage copied from the text: split it '
            "into several entries instead, one per place in the text."
        ]
    return [
        f"{label} is not a passage from the text shown — copy it character-for-character "
        f"(got: {quote.strip()[:120]!r})"
    ]


# --- the generic judge --------------------------------------------------------------------


def judge(
    profile: ProfileData,
    spec: CriterionSpec,
    *,
    task_id: str,
    source_description: str,
    corpus: str,
) -> Judgement:
    """One criterion, judged against one corpus, with its evidence grounded in it.

    Asks `SAMPLES` independent times and stops there when they agree; a split buys one more
    answer and the majority wins. Each sample is a whole `request_structured_output` call, so
    a sample that violates the output contract is fed back and retried on its own before it
    ever counts as a vote.

    Memoized by (task_id, profile): the task id names the question, and no two criteria
    share one — a shared judgement would need the other criterion's normative text, which
    an executor never receives.
    """

    def run() -> Judgement:
        verdicts: list[Verdict] = []
        usages: list[LlmUsage] = []
        while True:
            verdict, usage = _ask(spec, task_id, source_description, corpus)
            verdicts.append(verdict)
            usages.append(usage)
            answers = {v.passed for v in verdicts}
            if len(verdicts) >= SAMPLES and (len(answers) == 1 or len(verdicts) >= MAX_SAMPLES):
                return _decide(verdicts, usages)

    judged: Judgement = _memoized(task_id, profile, run)
    return judged


def _ask(
    spec: CriterionSpec, task_id: str, source_description: str, corpus: str
) -> tuple[Verdict, LlmUsage]:
    """One sample: one validated answer, or `AssessorExecutionError`."""
    payload, usage = request_structured_output(
        runtime.get_client(),
        task_id=task_id,
        model=JUDGE_MODEL,
        system_prompt=prompts.JUDGE_SYSTEM,
        user_prompt=prompts.JUDGE_USER.substitute(
            source_description=source_description,
            pass_condition=spec.pass_condition.strip(),
            failure_modes=_numbered(spec.failure_modes),
            max_evidence=MAX_EVIDENCE,
            corpus=corpus,
        ),
        validate=lambda answer: _validate_verdict(answer, corpus, len(spec.failure_modes)),
        temperature=tasks.TEMPERATURE,
        max_tokens=JUDGE_MAX_OUTPUT_TOKENS,
        reasoning=tasks.REASONING,
    )
    raw_mode = payload.get("failureMode")
    # Each quote is stored as the SOURCE spells it, not as the model rendered it.
    located = tuple(span for quote in payload["evidence"] if (span := locate(corpus, str(quote))))
    return (
        Verdict(
            reason=str(payload["reason"]).strip(),
            evidence=located,
            passed=bool(payload["verdict"]),
            failure_mode_index=int(raw_mode) if isinstance(raw_mode, int) else None,
        ),
        usage,
    )


def _decide(verdicts: Sequence[Verdict], usages: Sequence[LlmUsage]) -> Judgement:
    """The majority verdict, carrying the reason and quotes of a sample that voted for it.

    The winning sample's own words are kept rather than merged: a report shows one judge's
    account of one reading, which is checkable, instead of a synthesis nobody wrote.
    """
    answers = [verdict.passed for verdict in verdicts]
    majority = answers.count(True) > answers.count(False)
    return Judgement(
        verdict=next(verdict for verdict in verdicts if verdict.passed == majority),
        usage=_total(usages),
        agreed=answers.count(majority),
        samples=len(verdicts),
    )


def _total(usages: Sequence[LlmUsage]) -> LlmUsage:
    """What the whole vote spent — the samples summed, so cost per criterion stays readable."""
    return LlmUsage(
        model=usages[0].model,
        calls=sum(usage.calls for usage in usages),
        tokens_in=sum(usage.tokens_in for usage in usages),
        tokens_out=sum(usage.tokens_out for usage in usages),
        latency_ms=sum(usage.latency_ms for usage in usages),
        clean_retries=sum(usage.clean_retries for usage in usages),
    )


def _numbered(failure_modes: Sequence[str]) -> str:
    return "\n".join(f"{index}. {mode}" for index, mode in enumerate(failure_modes))


def _validate_verdict(answer: Any, corpus: str, failure_mode_count: int) -> list[str]:
    if not isinstance(answer, dict):
        return ['the answer must be a JSON object with "reason", "evidence" and "verdict"']
    violations: list[str] = []
    reason = answer.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        violations.append('"reason" must be a non-empty string')
    evidence = answer.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        violations.append('"evidence" must be a non-empty array of quoted passages')
    elif len(evidence) > MAX_EVIDENCE:
        # Checked before the quotes themselves: a runaway list would otherwise produce one
        # complaint per entry, and the feedback that goes back has to be readable.
        violations.append(
            f'"evidence" holds {len(evidence)} passages, more than the {MAX_EVIDENCE} a '
            "judgement may rest on. Quote only the places that decide it, once each."
        )
    else:
        seen: set[str] = set()
        for position, quote in enumerate(evidence):
            label = f'"evidence"[{position}]'
            if not isinstance(quote, str) or not quote.strip():
                violations.append(f"{label} must be a non-empty string")
                continue
            # Repeating a passage does not make it more evidence, and repetition IS the
            # shape a degenerating answer takes — one quote emitted until the budget ends.
            if quote.strip() in seen:
                violations.append(f"{label} repeats a passage already quoted; quote each once")
                continue
            seen.add(quote.strip())
            # The grounding rule: a citation that is not in the source is not evidence.
            violations.extend(_grounding_violations(label, quote, corpus))
    verdict = answer.get("verdict")
    if not isinstance(verdict, bool):
        violations.append('"verdict" must be true or false')
    mode = answer.get("failureMode")
    if verdict is False:
        if not isinstance(mode, int) or isinstance(mode, bool):
            violations.append(
                f'"failureMode" must be an integer from 0 to {failure_mode_count - 1} '
                "when the verdict is false"
            )
        elif not 0 <= mode < failure_mode_count:
            violations.append(
                f'"failureMode" {mode} is not one of the listed failures '
                f"(0 to {failure_mode_count - 1})"
            )
    elif verdict is True and mode is not None:
        violations.append('"failureMode" must be null when the verdict is true')
    return violations


# --- corpora (what each judged criterion is shown) ----------------------------------------
#
# Structure is decided here, in code, never by the model: which lesson is the opening and
# which is the closing follows the declared position, exactly as the pass conditions say.


def closing_lesson_body(profile: ProfileData) -> tuple[str, ProfileEntryData]:
    """The body of the last lesson by declared position, and the entry it came from."""
    bodies = profile.entries["lesson_bodies"]
    ordered = tasks.ordered_inventory(profile)
    if not ordered:
        raise AssessorExecutionError(
            "the lesson inventory is empty: no closing lesson to read", kind="profile"
        )
    closing_id = str(ordered[-1]["lessonId"])
    for lesson in bodies.value:
        if str(lesson.get("lessonId")) == closing_id:
            return str(lesson["body"]), bodies
    raise AssessorExecutionError(
        f"the profile carries no body for the closing lesson '{closing_id}' — "
        "a broken package, not a finding about its pedagogy",
        kind="profile",
    )


def arc_corpus(profile: ProfileData) -> str:
    """Both frame lessons at once: the criterion asks about the pair, not about either."""
    opening, _ = tasks.opening_lesson_body(profile)
    closing, _ = closing_lesson_body(profile)
    return f"FIRST LESSON OF THE COURSE:\n{opening}\n\nLAST LESSON OF THE COURSE:\n{closing}"


def _objectives_and_items_corpus(profile: ProfileData) -> tuple[str, list[dict[str, Any]]]:
    """The declared objectives beside the shipped items, with the items indexed.

    The indices are ours, assigned by position: the model answers with them, so a matched
    item resolves back to a row of the profile rather than to a name the model chose.

    Written as plain labelled lines, never serialized. A corpus that a task will demand
    VERBATIM quotes from must show the course's text exactly as the course writes it: JSON
    escaping turned `class="title"` into `class=\\"title\\"`, the model quoted what it could
    read, and the grounding check refused a citation that was correct — then the answer
    repeated, and the run died on it. Encoding the text and then asking for the decoded form
    back is the defect; another tolerance in `locate` would only have hidden it.
    """
    objectives = list(profile.entries["declared_objectives"].value)
    items = list(profile.entries["lesson_assessment_items"].value)
    objective_lines = "\n".join(
        f"{objective['id']}: {objective['outcome']}"
        + (
            f"\n  declared verification: {objective['verifiableBy']}"
            if isinstance(objective.get("verifiableBy"), str) and objective["verifiableBy"].strip()
            else "\n  declared verification: none"
        )
        for objective in objectives
    )
    corpus = f"OBJECTIVES:\n{objective_lines}\n\nASSESSMENT ITEMS:\n{_item_lines(items)}"
    return corpus, items


def _item_lines(items: Sequence[Mapping[str, Any]], with_lesson: bool = False) -> str:
    """One line per shipped item: our index, its kind, and its question as the course
    writes it. `with_lesson` adds where the item sits, which the reach task needs."""
    return "\n".join(
        f"[{index}] {item.get('kind')}"
        + (f" in lesson {item.get('lessonId')}" if with_lesson else "")
        + f": {item.get('prompt')}"
        for index, item in enumerate(items)
    )


# --- task: assessment mapping (extraction shared by two criteria) -------------------------


def assessment_mapping(profile: ProfileData) -> tuple[list[ObjectiveMapping], LlmUsage]:
    """Which shipped items measure which declared objective."""

    def run() -> tuple[list[ObjectiveMapping], LlmUsage]:
        corpus, items = _objectives_and_items_corpus(profile)
        objective_ids = [str(o["id"]) for o in profile.entries["declared_objectives"].value]
        payload, usage = request_structured_output(
            runtime.get_client(),
            task_id="assessment_mapping",
            model=ASSESSMENT_MAPPING_MODEL,
            system_prompt=prompts.ASSESSMENT_MAPPING_SYSTEM,
            user_prompt=prompts.ASSESSMENT_MAPPING_USER.substitute(corpus=corpus),
            validate=lambda answer: _validate_mapping(answer, corpus, objective_ids, len(items)),
            temperature=tasks.TEMPERATURE,
            max_tokens=EXTRACTION_MAX_OUTPUT_TOKENS,
            reasoning=tasks.REASONING,
        )
        by_id = {str(entry["objectiveId"]): entry for entry in payload["objectives"]}
        mapped = [
            ObjectiveMapping(
                objective_id=objective_id,
                reason=str(by_id[objective_id]["reason"]).strip(),
                evidence=locate(corpus, str(by_id[objective_id]["evidence"])) or "",
                item_indices=tuple(int(i) for i in by_id[objective_id]["itemIndices"]),
            )
            for objective_id in objective_ids
        ]
        return mapped, usage

    result, usage = _memoized("assessment_mapping", profile, run)
    return list(result), usage


def _validate_mapping(
    answer: Any, corpus: str, objective_ids: Sequence[str], item_count: int
) -> list[str]:
    violations = _shape_violations(answer, "objectives")
    if violations:
        return violations
    expected = set(objective_ids)
    seen: set[str] = set()
    for position, entry in enumerate(answer["objectives"]):
        label = f"objectives[{position}]"
        if not isinstance(entry, dict):
            violations.append(f"{label} must be an object")
            continue
        objective_id = entry.get("objectiveId")
        if not isinstance(objective_id, str) or objective_id not in expected:
            violations.append(
                f"{label}.objectiveId must be one of the given ids (got {objective_id!r})"
            )
        elif objective_id in seen:
            violations.append(f"{label}.objectiveId {objective_id!r} appears more than once")
        else:
            seen.add(objective_id)
        if not isinstance(entry.get("reason"), str) or not str(entry.get("reason")).strip():
            violations.append(f"{label}.reason must be a non-empty string")
        evidence = entry.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            violations.append(f"{label}.evidence must be a non-empty string")
        else:
            violations.extend(_grounding_violations(f"{label}.evidence", evidence, corpus))
        indices = entry.get("itemIndices")
        if not isinstance(indices, list):
            violations.append(f"{label}.itemIndices must be an array")
        else:
            # No duplicates, which also bounds the list: it cannot be longer than the number
            # of items, so a repeating answer is refused instead of growing without end.
            listed: set[int] = set()
            for value in indices:
                if not isinstance(value, int) or isinstance(value, bool):
                    violations.append(f"{label}.itemIndices must hold integers (got {value!r})")
                elif not 0 <= value < item_count:
                    violations.append(
                        f"{label}.itemIndices holds {value}, which is not an item index "
                        f"(0 to {item_count - 1})"
                    )
                elif value in listed:
                    violations.append(f"{label}.itemIndices lists item {value} more than once")
                else:
                    listed.add(value)
    if not violations and seen != expected:
        violations.append(f"missing an entry for objective id(s): {sorted(expected - seen)}")
    return violations


def verification_corpus(profile: ProfileData, mappings: Sequence[ObjectiveMapping]) -> str | None:
    """The objectives the verification criterion is actually about, with their items.

    Narrowed in CODE, not by the judge: the criterion excludes objectives with no declared
    `verifiableBy` (a structural fact anyone can read off the profile) and there is nothing
    to compare for an objective no item bears on. `None` means the set is empty, which is a
    vacuous pass rather than a question worth asking.
    """
    objectives = {str(o["id"]): o for o in profile.entries["declared_objectives"].value}
    items = list(profile.entries["lesson_assessment_items"].value)
    blocks: list[str] = []
    for mapping in mappings:
        objective = objectives.get(mapping.objective_id)
        if objective is None or not mapping.item_indices:
            continue
        verifiable_by = objective.get("verifiableBy")
        if not isinstance(verifiable_by, str) or not verifiable_by.strip():
            continue
        measured = "\n".join(
            f"  - {items[index].get('kind')}: {items[index].get('prompt')}"
            for index in mapping.item_indices
            if index < len(items)
        )
        blocks.append(
            f"OBJECTIVE {mapping.objective_id}: {objective['outcome']}\n"
            f"DECLARED VERIFICATION: {verifiable_by}\n"
            f"ITEMS THAT MEASURE IT:\n{measured}"
        )
    return "\n\n".join(blocks) if blocks else None


# --- task: assessment reach (extraction; the count is the executor's) ---------------------


def assessment_reach(profile: ProfileData) -> tuple[list[ItemReach], LlmUsage]:
    """Which lessons each shipped assessment item draws on."""

    def run() -> tuple[list[ItemReach], LlmUsage]:
        ordered = tasks.ordered_inventory(profile)
        items = list(profile.entries["lesson_assessment_items"].value)
        lesson_ids = [str(lesson["lessonId"]) for lesson in ordered]
        # Plain lines, not JSON: same reason as the mapping corpus above.
        plan_lines = "\n".join(f"{lesson['lessonId']}: {lesson.get('title')}" for lesson in ordered)
        corpus = (
            f"LESSON PLAN IN DELIVERY ORDER:\n{plan_lines}\n\n"
            f"ASSESSMENT ITEMS:\n{_item_lines(items, with_lesson=True)}"
        )
        payload, usage = request_structured_output(
            runtime.get_client(),
            task_id="assessment_reach",
            model=ASSESSMENT_REACH_MODEL,
            system_prompt=prompts.ASSESSMENT_REACH_SYSTEM,
            user_prompt=prompts.ASSESSMENT_REACH_USER.substitute(corpus=corpus),
            validate=lambda answer: _validate_reach(answer, lesson_ids, len(items)),
            temperature=tasks.TEMPERATURE,
            max_tokens=EXTRACTION_MAX_OUTPUT_TOKENS,
            reasoning=tasks.REASONING,
        )
        by_index = {int(entry["index"]): entry for entry in payload["items"]}
        reached = [
            ItemReach(
                index=index,
                reason=str(by_index[index]["reason"]).strip(),
                references=tuple(str(ref) for ref in by_index[index]["referencesLessonIds"]),
            )
            for index in range(len(items))
        ]
        return reached, usage

    result, usage = _memoized("assessment_reach", profile, run)
    return list(result), usage


def _validate_reach(answer: Any, lesson_ids: Sequence[str], item_count: int) -> list[str]:
    violations = _shape_violations(answer, "items")
    if violations:
        return violations
    known = set(lesson_ids)
    seen: set[int] = set()
    for position, entry in enumerate(answer["items"]):
        label = f"items[{position}]"
        if not isinstance(entry, dict):
            violations.append(f"{label} must be an object")
            continue
        index = entry.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < item_count:
            violations.append(f"{label}.index must be an integer between 0 and {item_count - 1}")
        elif index in seen:
            violations.append(f"{label}.index {index} appears more than once")
        else:
            seen.add(index)
        if not isinstance(entry.get("reason"), str) or not str(entry.get("reason")).strip():
            violations.append(f"{label}.reason must be a non-empty string")
        references = entry.get("referencesLessonIds")
        if not isinstance(references, list):
            violations.append(f"{label}.referencesLessonIds must be an array")
        else:
            # Membership plus no duplicates bounds the list at the size of the plan. This is
            # the array that once filled with repeated and then invented ids until the whole
            # budget was gone; either half alone would have let it run.
            drawn: set[str] = set()
            for value in references:
                # The closed-set equivalent of the grounding rule: a lesson the plan does
                # not declare is an invented one, and the executor would count it.
                if not isinstance(value, str) or value not in known:
                    violations.append(
                        f"{label}.referencesLessonIds holds {value!r}, which is not a lesson "
                        "identifier from the plan"
                    )
                elif value in drawn:
                    violations.append(
                        f"{label}.referencesLessonIds names lesson {value!r} more than once"
                    )
                else:
                    drawn.add(value)
    if not violations and len(seen) != item_count:
        violations.append(
            f"missing an entry for item index(es): {sorted(set(range(item_count)) - seen)}"
        )
    return violations


def _shape_violations(answer: Any, key: str) -> list[str]:
    if not isinstance(answer, dict):
        return [f'the answer must be a JSON object with a "{key}" array']
    if not isinstance(answer.get(key), list):
        return [f'"{key}" must be an array']
    return []
