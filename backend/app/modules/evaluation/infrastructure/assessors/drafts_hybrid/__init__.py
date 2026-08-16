"""`drafts-hybrid` v12 — the `course-drafts-qa` lineage's LLM-carrying assessor.

v12 makes the verification judge point instead of transcribe, and adds its verdict up in
code. Six repeats of one draft under v11 — same course, same instrument, same assessor —
answered one dead run, four fails and one pass, and `assessment_verification_match` spent
**21 calls on 6 verdicts, 9 of them retries**. Reading the traces, two of the three causes
were ours and are fixed here; the third is the instrument's and is deliberately not touched,
because moving the mechanism and the bar in the same round leaves the next campaign unable
to say which did what.

**The corpus is a template, and a model asked to copy from it splices.** Every task is shown
under the same label and this generator opens every proposal with the same sentence, so an
answer came back quoting *"proposed exercise (codeChallenge): The student needs to practice
navigating a directory structure using Tab completion"* — the prefix of one task carrying the
body of another. The grounding check refused it, correctly, and the retry never converged: 8
calls, no result. Citing by NUMBER removes the class outright, and it is the same closed-set
rule `assessment_reach` has used since v3: a number the objective's own block did not list is
refused like a hallucinated quote, and the passage a report finally shows is fetched from the
profile — the course's own text rather than the label this package prints around it, which is
ADR-0009 more exactly than a transcription ever was. The mapping loses its quote for the same
reason; it is the field that killed a run in the previous campaign.

**One verdict over four objectives made the model do the arithmetic.** A sample wrote
"satisfied except obj-3, whose removal tasks are recognition items" and answered TRUE; two
others agreed on a failure while naming different objectives and picking different failure
modes. The judge now answers ONE ENTRY PER OBJECTIVE — reason, cited task numbers, satisfied,
and the declared mode when not — and the criterion is the conjunction, computed here. What is
voted on is still the criterion's verdict, so `SAMPLES` and the tie-break are unchanged, and
`verification_failed_by_sample` reports which objectives each sample failed: samples that
disagree about WHICH objective disagree about the facts, and samples that name the same one
and split disagree about the bar. Only the second is a bug report about the instrument.

**And three things about citations that the field runs of this very version taught.** A list
marker is formatting: `locate` already ignored whitespace and emphasis and now ignores the
bullet or ordinal too, because a quote running from a lead-in into the list under it was being
refused for a `- ` the course put there. The first attempt dropped the marker only where the
SOURCE has it, at the start of a line, and that merely turned the false negative around — a
model that copied the ordinal faithfully became the one refused, at 9 retries in 5 runs. The
marker is invisible **wherever a break puts it**, on both sides of the comparison, which is
the only symmetric reading. The rule itself moved to `grounding.py` because
`outcomes_extraction` was not using it at all: that validator compared bytes against the
lesson body while every other citation went through `locate`, which is why it was the most
retried task in the package (7 in 13 calls, then 5 in 10). And an index a model serializes as
`"0"` is now read as `0` — two of five runs met an upstream that quotes its integers and one
died on it, spending its attempts fixing the type and then dropping an entry of the twenty.
How an answer is encoded is not what it says, which is the tolerance `_parse_json` already
grants a markdown fence.

Untouched on purpose: the shared `JUDGE_USER` and the four criteria that read a lesson body
(they have not failed once), the vote, the retry ladder, the budgets, and the bar itself —
the sentence about partial satisfaction travels verbatim from the shared judge prompt.

v11 reads the assessment a draft PROPOSES, not only the half it delivers (ADR-0046). The
three criteria that read assessment now take `assessment_offerings` — everything the draft
offers to assess with, every entry marked `delivered` or `proposed` — where they used to take
`lesson_assessment_items`. Measured over the five drafts on hand, that is 5, 8, 14, 10 and 14
proposed exercises against 5, 12, 3, 3 and 3 delivered items: the corpus these three tasks
were reading was between 18 % and 60 % of what each draft actually offers, and the five
objectives the v6 era reported as measured by nothing are covered by proposals. Their
failures were findings about the extraction.

Three things follow, and each is identity. **The corpora show one index space** over
delivered and proposed together, each entry marked and separated by a blank line, because a
proposed exercise's prompt runs over several lines and the old one-line-per-item layout would
have let a single task read as several — the model would answer with indices nobody assigned.
**The two extraction prompts say what a proposal is** ("what the course commits to asking of
the learner"), so the model is not left to decide whether something unbuilt counts; the answer
fields are renamed with them (`taskIndices`, `tasks`), because a field called `itemIndices`
under a prompt about tasks invites exactly the reading this bump removes. And
`cr-every-objective-has-an-assessment-item` **reports how much of its coverage rests on
proposals alone** (`objectives_measured_by_proposal_only`, `assessment_offered`): the
proposals are written by the same pipeline as the objectives, so alignment between them may
be partly tautological, and the metric is what makes that measurable rather than arguable.

The judging prompt, the vote, the retry ladder and the other four judged criteria are
untouched. The instrument moves with this: `course-drafts-qa` v7 is what re-points those
three criteria and states in each pass condition which kinds it counts.

v10 tells the outcomes extraction which verb to report when the statement wraps its action.
Reading the eleven runs of the v6 era found the task taking the auxiliary of the wrapper as
the verb and marking as non-observable content that is observable: *"you will be able to
read, write, and structure your own web pages"* answered `be able to`, *"you'll go from
writing plain, unstyled HTML pages to confidently styling…"* answered `go` — while the SAME
structure, *"you will be able to contribute to any repository"*, answered `contribute` in
another draft. Inconsistency, not a rule the model was following, and the same class as the
historic `learn` case. The prompt now says to look through an enabling phrase and report the
verb of the action, to take the first when several are named, and to report the wrapper
phrase itself when there is no action behind it — a state about a topic is not an observable
action, which is the answer the criterion is written to catch. The suspected mechanism is
worth recording: the task's own framing line asks for what the learner will BE ABLE TO DO,
so the prompt primed the very phrase that came back as the verb.

Two remedies were available and rejected. **The validator was not touched**: making the rule
a contract the retry loop enforces means rejecting `verb` values from a wrapper list, and
`be familiar with`, `learn about` and `understand` are exactly the answers a truthful
extraction must be able to give — a deny-list would force a false answer whenever the
statement genuinely has no action behind it. And **the framing line was left alone**: it is
the likely cause, but rewording it moves which statements are LISTED, which is a different
criterion's evidence and would leave the field verification with two variables. The rule
overrides the priming without moving the statement set. `objectives_classification` carries
the same field and the same risk and is also untouched, because the same reading found it
resolving correctly in all three drafts.

v9 declares which upstreams may NOT serve its calls (ADR-0038): `sail-research`, whose
serving produced every capped runaway of the campaign — seven of seven, reasoning past
both disable flags into the judging budget, one four-draw streak beating the clean retry —
and `atlas-cloud`, which billed invisible reasoning at 11–100× the visible answer and once
returned a null-content 200. The router draws an upstream per request, so the pool of
possible judges is identity: the list is pinned beside the retry constants, declared in
`SOURCE_CONFIG`, and travels per request as a provider preference through the same
extra-wire-fields seam the reasoning flags use. Editing the list — either direction — is a
version bump.

v8 lets an answer cut at the token budget buy the clean-conversation retry that v6 gave
degeneration alone. The v1 lesson said `finish_reason: length` is deterministic and
retrying never recovered one — measured over feedback retries, where the broken answer
re-enters the same conversation. The field runs sharpened it twice: first to "deterministic
per provider" (every capped runaway of the campaign came from one upstream), then the
retry's own first save refuted even that — the same provider cut one answer and served a
clean one seconds later. Runaways are **stochastic per request**, strongly
provider-correlated, and a conversation rebuilt from scratch re-rolls the serving itself;
one attempt buys that re-roll, a second identical cut says the question invites it.
`CLEAN_RETRY_KINDS` is declared in `SOURCE_CONFIG` because which failures may be retried
decides which verdict survives.

v7 says "no reasoning" in both of the words a provider might understand:
`reasoning: {effort: "none", enabled: false}`. OpenRouter documents `effort` for
OpenAI/Grok models, not this family, so for some upstreams v6's `effort: "none"` was
never an instruction at all — the first v6 calibration met one that reasoned for 36
seconds and billed 3,491 output tokens for a 60-token answer, and another that returned
its entire reasoning with a null answer (an `execution_error` the failure budget
absorbed). `enabled` is the boolean OpenRouter can translate more broadly; sending both
is belt and braces, not a guarantee — an upstream that ignores the whole `reasoning`
object still ignores it, which is the open provider-pinning question, not this bump's.
Whether the model may reason is identity (ADR-0034 §1), so this is a version.

v6 changed how a failing conversation is retried, and nothing about what is asked
(ADR-0037 §7). The feedback loop realized v5's failures are two shapes wearing one
remedy: a **contract violation** is a fixable mistake and keeps the feedback retry, which
the campaign measured to work; a **degeneration** — the model repeating its answer
verbatim after being told what was wrong — is not, because feeding the broken answer back
puts the loop in the context. A degeneration now buys ONE retry on a clean conversation,
rebuilt from scratch; a second identical degeneration raises, being the poison case.
Transport, configuration and `finish_reason: length` are never clean-retried. Every
failure now carries a machine-readable kind, failures are memoized like answers (the
criteria sharing a task degrade together, without re-asking a question that just
degenerated), and each task reports `clean_retries` in its `llm_*` metric — a verdict
that needed a fresh conversation is a shifted population, and calibration must see it.
The retry conversation shapes which answer finally arrives, so this is identity and v5's
calibration does not transfer.

v5 answered what repeated runs of v4 measured, in two places that have nothing to do with
each other except that the same campaign found both.

**A judgement is now decided by a vote.** Repeats of one question over one text disagree:
the variance outlives temperature 0, because it comes from how the server batches work
rather than from how tokens are drawn. Two samples are asked, a third only when they split,
and the majority wins — which is exactly the verdict an always-three majority would give,
since two agreeing samples cannot be overturned. The split itself is reported per criterion
and is worth as much as the verdict: every under-specified criterion found so far was found
by noticing the model agree on the facts and divide on whether they clear the bar. Voting is
not the main remedy for that — writing the missing threshold into the instrument is, and it
removes far more disagreement than sampling ever will — but borderline instances surface one
per draft, so there is no list of "hard criteria" to sample selectively instead.

**Grounding stopped rejecting quotes over markdown.** Lesson bodies are markdown; a model
quoting a sentence that carries `**bold**` drops the markers about as often as it keeps them,
and byte comparison called that a hallucination. Emphasis is invisible to the match now, the
same way whitespace already was, and the stored quote is still the source's own span.

**And a judgement is bounded twice over, because one bound was not enough.** v4 made the
evidence a list, since findings rest on several places at once; unbounded, that turned out to
be a way to spend the whole output budget on nothing — one answer looped a nine-quote cycle
until the token limit cut it off at 191 entries, 18 of them distinct. `MAX_EVIDENCE` caps what
a judgement may CONTAIN, checked before the quotes are so the complaint that goes back is one
line rather than one per entry. But it is checked after the answer arrives, so it stops the
garbage being stored and not the minutes being paid: the next degeneration repeated a single
sentence into the array, ran to the 8000-token budget three times over, and cost nine minutes
before the evaluation died. `JUDGE_MAX_OUTPUT_TOKENS` is the other half — a judging call is
given roughly twice the widest real answer rather than the extraction tasks' budget, so a
model that starts looping is cut off in seconds. A vote pays for all of this twice.

v4 fixed what the first calibration runs of v3 found: the evidence contract asked for ONE
continuous quote from judgements that rest on several places in the text, so a correct
verdict was rejected for how it was cited. Three changes, all of them identity. `evidence`
is now a LIST, one entry per place, each still a continuous span. Grounding tolerates
whitespace differences when MATCHING while storing the source's own span, because a model
that quotes across an indented line renders the indent as a space and that is not a finding
about the course. And the feedback names the rule that was broken rather than the symptom,
because told only "not verbatim" the model answered the same thing three times — a case the
retry loop now stops on, since at temperature 0 an identical answer is a fixed answer and
the remaining budget buys nothing. Same prompts otherwise, same models, same decision
constants; the bump is what keeps v3's calibration from transferring to a judge that is
asked for its evidence differently.

v3 took the first seven criteria whose verdict is the MODEL's. Everything before it kept
the model on the supply side — it extracted or classified, and code decided — because that
half was cheaper and because a decision rule in code is a decision rule anyone can read.
The sixteen abstentions marked "requires semantic judgment" have no mechanical proxy at
all, and seven of them are reachable without reading every lesson: the two frame lessons,
the objectives against the shipped assessment, and what that assessment draws on. Those
seven cost one call each and take coverage from 12 of 29 to 19; the other nine need a call
per lesson (or per pair, or per module) and are deliberately not taken here.

What keeps a judged criterion reviewable is in `judgments.py` and holds for all seven: the
question is the instrument's own `pass_condition`, quoted verbatim and never retyped into
this package; the answer carries a passage checked to be verbatim in the text shown; and a
`fail` names which of the criterion's DECLARED failure modes it saw. The judge decides,
inside a vocabulary it did not write.

Two of the seven are not judgements at all, and it is worth saying which: "every objective
has an assessment item" is arithmetic over a mapping the model supplies, and "assessment
reaches back" is a count over lesson references constrained to the identifiers the plan
declares. They sit here because the mapping needs a model, not because the verdict does.

v2 differed from v1 in sampling and nothing else: the model asks for no reasoning and the
output budget has room for an answer. v1 could not finish a run — its 2048-token budget
was spent entirely on the model's own thinking, so the semantic tasks came back empty
every time (the calibration traces recorded 2048–2325 reasoning tokens and no content).
That sampling is unchanged in v3, and the judging prompts get the effect of thinking a
different way: they ask for the reason BEFORE the verdict, so the model works through the
text in the answer it is billed for rather than in reasoning it is billed for twice.

Hybrid in ADR-0016's own sense ("the hybrid is the norm"): one artifact, one identity,
and per criterion whatever mechanism the criterion needs. Seven executors are pure code —
a COPY of `drafts-structural` v1's, not an import, because shared code would tie the two
identities together. Five are semantic: an LLM extracts or classifies (outcome statements
and their verbs, Bloom levels of objectives, sophistication of the planned concepts) and
the executor decides pass/fail deterministically over what came back. Seven are the v3
additions above.

It is ONE artifact rather than a separate LLM-only assessor because judgments do not
combine across assessors: the report and the fitness read the most recent judgment per
content, so a second assessor's evaluation would REPLACE the structural coverage instead
of adding to it. One artifact, one judgment, full coverage.

Identity (ADR-0034): the models, prompts, temperature, schemas and decision constants are
this assessor's identity, pinned in code and declared in `SOURCE_CONFIG` — including a
fingerprint of the prompt texts, so a prompt edited without a VERSION bump is refused at
ratification. The transport (key, base URL, backoff) is environment and re-versions
nothing. When a task genuinely cannot answer it raises `AssessorExecutionError` with its
kind and task; what that costs — a criterion's `execution_error` or, past the failure
budget, the whole evaluation — is the derivation's decision, not this package's
(ADR-0037; until its third PR lands, every failure still aborts the evaluation whole).

`cr-objectives-verb-level-band` stays abstained ON PURPOSE: it compares objectives against
the declared difficulty, and this format declares `difficulty` only sometimes (a nullable
field inside `course_descriptor`). An executor can only answer pass or fail, and neither
is honest against a null anchor. The clean exit is a `declared_difficulty` data
requirement whose absence derives `no_evidence` mechanically — an instrument and adapter
change, deliberately not taken here.

Any change here — an executor, a prompt, a model, a constant, the mapping, an
abstention — is a NEW VERSION and a new identity (ADR-0016 clause 2); ratifying new
instrument versions is not a change (ADR-0019).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from app.modules.evaluation.domain.model import Coverage
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    executors,
    judgments,
    prompts,
    structured_output,
    tasks,
)

NAME = "drafts-hybrid"
VERSION = "12"
INSTRUMENT_ID = "course-drafts-qa"


@contextmanager
def cache_scope() -> Iterator[None]:
    """One evaluation's memory of what it asked, forgotten on the way out (`memo.py`).

    Entered by whoever runs an evaluation, so two of them — sequential in one thread or
    concurrent in several — never see each other's answers. That isolation is what makes
    two runs over one content two samples instead of one answer read twice.
    """
    with tasks.cache_scope(), judgments.cache_scope():
        yield


def clear_caches() -> None:
    """Empty both caches of the CURRENT scope, without leaving it."""
    tasks.clear_task_cache()
    judgments.clear_judgment_cache()


EXECUTORS = {
    # The structural seven (copied from drafts-structural v1).
    "cr-objectives-min-count": executors.objectives_min_count,
    "cr-audience-declared": executors.audience_declared,
    "cr-prerequisites-declared": executors.prerequisites_declared,
    "cr-module-structure-well-formed": executors.module_structure_well_formed,
    "cr-course-opens-with-general-intro": executors.course_opens_with_general_intro,
    "cr-course-has-development": executors.course_has_development,
    "cr-no-lesson-spikes-in-lexical-load": executors.no_lesson_spikes_in_lexical_load,
    # The semantic five: LLM extraction/classification, deterministic decision.
    "cr-objectives-observable-verbs": executors.objectives_observable_verbs,
    "cr-outcomes-present": executors.outcomes_present,
    "cr-outcomes-observable-verbs": executors.outcomes_observable_verbs,
    "cr-objectives-non-decreasing-demand": executors.objectives_non_decreasing_demand,
    "cr-cognitive-demand-rises-across-the-course": (
        executors.cognitive_demand_rises_across_the_course
    ),
    # The judged seven (v3): one call each, no per-lesson fan-out.
    "cr-opening-lesson-connects-backwards": executors.opening_lesson_connects_backwards,
    "cr-closing-lesson-integrates": executors.closing_lesson_integrates,
    "cr-closing-lesson-projects-forward": executors.closing_lesson_projects_forward,
    "cr-arc-character": executors.arc_character,
    "cr-every-objective-has-an-assessment-item": (executors.every_objective_has_an_assessment_item),
    "cr-assessment-matches-the-declared-verification": (
        executors.assessment_matches_the_declared_verification
    ),
    "cr-assessment-retrieves-earlier-taught-material": (
        executors.assessment_retrieves_earlier_taught_material
    ),
}

ABSTENTIONS = {
    # Abstained for a reason of THIS format, not of this assessor's mechanism: the band
    # needs the declared difficulty as its anchor, and the format declares it only
    # sometimes (nullable inside `course_descriptor`). Executable once the lineage mints
    # `declared_difficulty` and the adapter supplies it — absence would then derive
    # `no_evidence` mechanically instead of forcing a verdict against a null anchor.
    "cr-objectives-verb-level-band": (
        "requires a declared difficulty this format supplies only sometimes; judging a "
        "band against a null anchor is not honest"
    ),
    # What is left of the judgment backlog after v3, and it is one shape: every one of
    # these reads EVERY lesson body — one call per lesson, per pair or per module, which
    # takes an evaluation from ~10 calls to ~40-50 and makes an all-or-nothing run
    # (ADR-0034 §4) a bad bet. Taking them is a later version, and the failure-isolation
    # decision it needs is not made yet.
    "cr-module-single-topic": "requires semantic judgment of topical focus, per module",
    "cr-new-instruction-is-preceded-by-a-problem": (
        "requires semantic identification of new instructional material and of what "
        "motivates it, per lesson"
    ),
    "cr-later-lessons-apply-earlier-concepts": (
        "requires a concept map extracted from every lesson body"
    ),
    "cr-adjacent-pair-has-a-bridge": (
        "requires semantic judgment of whether a lesson pair states its relation, per pair"
    ),
    "cr-concepts-introduced-before-use": (
        "requires a concept map extracted from every lesson body"
    ),
    "cr-every-objective-is-developed-somewhere": (
        "requires semantic matching of each declared objective against every lesson body"
    ),
    "cr-every-substantive-lesson-serves-an-objective": (
        "requires semantic matching of every lesson body against the declared objectives"
    ),
    "cr-lesson-works-at-the-level-its-objective-demands": (
        "requires semantic classification of the cognitive level each lesson body works at"
    ),
    "cr-skill-lessons-carry-a-worked-example": (
        "requires semantic identification of introduced skills and of worked examples, per lesson"
    ),
}

# Derived from the executor dict itself — no parallel list to drift.
COVERAGE = Coverage(executes=frozenset(EXECUTORS), abstains=ABSTENTIONS)

SOURCE_CONFIG = {
    "name": NAME,
    "version": VERSION,
    "instrumentId": INSTRUMENT_ID,
    "coverage": {
        "executes": sorted(EXECUTORS),
        "abstains": dict(sorted(ABSTENTIONS.items())),
    },
    # The semantic identity, declared (ADR-0034): which models judge which tasks, at what
    # temperature, asking exactly these prompts. The ratification guard compares this
    # against the stored config, so none of it can drift without a VERSION bump.
    "llm": {
        "provider": "openrouter",
        "temperature": tasks.TEMPERATURE,
        # Declared because they decide the answer, not merely how it travels: the budget
        # is what the thinking competes for, and whether there is thinking at all is what
        # v1 lost every run to (ADR-0034 §1 — sampling is identity).
        "maxOutputTokens": tasks.MAX_OUTPUT_TOKENS,
        "reasoning": dict(tasks.REASONING),
        # How many answers a judgement is decided by. Declared because it decides what the
        # verdict IS, not merely how it travels: changing either number changes which
        # answers survive a disagreement.
        "samples": {"asked": judgments.SAMPLES, "max": judgments.MAX_SAMPLES},
        # Declared for the same reason: it bounds what an answer may contain, and the
        # prompt states it, so it shapes what comes back rather than merely how it travels.
        "maxEvidence": judgments.MAX_EVIDENCE,
        # What an answer may cost is as much a part of what comes back as what it may
        # contain. Judging and the two extraction tasks are bounded apart, because their
        # honest sizes differ by an order of magnitude.
        "judgeMaxOutputTokens": judgments.JUDGE_MAX_OUTPUT_TOKENS,
        "extractionMaxOutputTokens": judgments.EXTRACTION_MAX_OUTPUT_TOKENS,
        # How a failing conversation is retried decides which answer finally arrives
        # (ADR-0037 §7): these kinds may buy this many fresh conversations.
        "cleanRetries": {
            "max": structured_output.MAX_CLEAN_RETRIES,
            "kinds": list(structured_output.CLEAN_RETRY_KINDS),
        },
        # Which upstreams may not serve a call decides which judge answers it
        # (ADR-0038): the pool is identity, like the model ids that name it.
        "deniedProviders": list(structured_output.DENIED_PROVIDERS),
        "models": {
            "outcomes_extraction": tasks.OUTCOMES_EXTRACTION_MODEL,
            "objectives_classification": tasks.OBJECTIVES_CLASSIFICATION_MODEL,
            "concept_trajectory": tasks.CONCEPT_TRAJECTORY_MODEL,
            "judge": judgments.JUDGE_MODEL,
            "assessment_mapping": judgments.ASSESSMENT_MAPPING_MODEL,
            "assessment_reach": judgments.ASSESSMENT_REACH_MODEL,
        },
        "promptsFingerprint": prompts.fingerprint(),
    },
}
