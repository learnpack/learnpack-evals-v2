"""The prompts of `drafts-hybrid`'s semantic tasks — assessor IDENTITY (ADR-0034).

Editing any template here changes what the judge asks, which changes the judge: it is a
new version of `drafts-hybrid`, exactly like editing an executor. The fingerprint below
travels in `SOURCE_CONFIG`, so a prompt edited without a VERSION bump is refused at
ratification (the stored config no longer matches the code).

Templates use `string.Template` (`$placeholder`) because the JSON shapes they show the
model are full of braces that `str.format` would eat.

Duplicated per assessor on purpose, industry names kept on purpose: this is the ACL side
of the GLOSSARY's equivalence table, where *extraction*, *classification* and *structured
output* mean what the industry means by them.
"""

import hashlib
from string import Template

# --- outcomes extraction (the opening lesson's promises to the learner) -----------------

OUTCOMES_EXTRACTION_SYSTEM = """\
You extract information from educational course text. Answer with a single JSON object
and nothing else — no prose, no markdown fences. Every value described as verbatim must
be copied character-for-character from the source text."""

OUTCOMES_EXTRACTION_USER = Template(
    """\
Below is the body of the OPENING lesson of a course, between <lesson> tags.

List every outcome statement it makes to the learner: a statement of what the learner
will BE ABLE TO DO after the course. Topics the course will cover, descriptions of the
course's content and invitations to enjoy it are NOT outcome statements.

Answer with this JSON shape:
{"outcomes": [{"statement": "<one outcome sentence, copied verbatim from the lesson>",
"verb": "<the main action verb of the outcome, lowercase>",
"is_observable": <true if the verb names an observable action such as build, write,
classify, solve; false if it names an internal state such as understand, know,
learn about, be familiar with>}]}

If the lesson states no outcomes, answer {"outcomes": []}.

<lesson>
$body
</lesson>"""
)

# --- objectives classification (verb + cognitive level per declared objective) ----------

OBJECTIVES_CLASSIFICATION_SYSTEM = """\
You classify learning objectives from educational courses. Answer with a single JSON
object and nothing else — no prose, no markdown fences."""

OBJECTIVES_CLASSIFICATION_USER = Template(
    """\
Below are the learning objectives a course declares, one per line, each preceded by its
index, between <objectives> tags.

For EACH objective, classify:
- "verb": the main action verb of the objective, lowercase.
- "is_observable": true if the verb names an observable action (build, write, classify,
  solve, deploy); false if it names an internal state (understand, know, learn about,
  be familiar with) that cannot be verified by watching the learner.
- "bloom_level": the cognitive level the objective demands, per the Revised Bloom
  taxonomy — exactly one of: "remember", "understand", "apply", "analyze", "evaluate",
  "create".

Answer with this JSON shape:
{"objectives": [{"index": <the objective's index>, "verb": "...",
"is_observable": <true|false>, "bloom_level": "..."}]}

Exactly one entry per objective, in the order given.

<objectives>
$objectives
</objectives>"""
)

# --- concept trajectory (sophistication of reasoning along the declared plan) -----------

CONCEPT_TRAJECTORY_SYSTEM = """\
You classify the cognitive sophistication of lessons in an educational course plan.
Answer with a single JSON object and nothing else — no prose, no markdown fences."""

CONCEPT_TRAJECTORY_USER = Template(
    """\
Below is a course plan in delivery order, between <plan> tags: one lesson per line, as a
JSON object with the lesson's identifier, title, delivery type and the concept it
declares it covers (null when the plan names none). The course-level opening and closing
lessons have already been removed.

For EACH lesson, classify the sophistication of the reasoning it demands from the
learner, as an integer from 1 to 5:
1 = recall or recognition of isolated facts or terms
2 = comprehension of a single concept in isolation
3 = application of a concept to a concrete task
4 = analysis or combination of several concepts
5 = evaluation, design or creation integrating multiple concepts

Judge from what the plan declares — the title, the type and the concept — not from what
the lessons might contain.

Answer with this JSON shape:
{"lessons": [{"lessonId": "<identifier exactly as given>", "level": <1 to 5>}]}

Exactly one entry per lesson, in the order given.

<plan>
$plan
</plan>"""
)

# --- the judging prompts (v3) -----------------------------------------------------------
#
# These ask for a VERDICT, which the extraction prompts above never do. Three rules shape
# all of them and none is cosmetic:
#
# 1. The normative text is NOT written here. Each user prompt receives the criterion's own
#    `pass_condition` and `failure_modes` from the instrument, so the judge is asked
#    exactly what the published instrument says and there is one source of truth. The
#    consequence is deliberate: bumping the INSTRUMENT changes what the judge asks without
#    moving this file's fingerprint (ADR-0019 governs that act; see the module docstring
#    of `judgments.py`).
# 2. The answer's field order is `reason` -> `evidence` -> `verdict`, and the shape shown
#    to the model says so. JSON mode emits fields in the order the model writes them, so a
#    verdict-first shape would have it commit before reading its own reasoning; this order
#    is what buys the effect of thinking without paying for reasoning tokens.
# 3. Every verdict carries a verbatim quote, checked against the text shown (ADR-0009). The
#    prompts say "copied character-for-character" because that is what the validator tests.

JUDGE_SYSTEM = """\
You judge drafts of educational courses against one explicit criterion at a time. You are
strict and literal: you judge what the text does, not what it could plausibly have meant.
Answer with a single JSON object and nothing else — no prose, no markdown fences.

Every judgement must quote its evidence: a passage copied character-for-character from the
text you were shown. Never paraphrase a quote, and never quote text that is not there — if
you can find no passage supporting a positive verdict, the verdict is false."""

JUDGE_USER = Template(
    """\
Below, between <source> tags, is $source_description of a draft course.

Judge it against this criterion, and against nothing else:

$pass_condition

These are the ways this criterion is known to fail, numbered:
$failure_modes

Answer with this JSON shape, in this field order:
{"reason": "<one sentence saying what the text does, in your own words>",
"evidence": ["<one continuous passage copied verbatim from the text below>", "..."],
"verdict": <true if the criterion is satisfied, false if it is not>,
"failureMode": <when the verdict is false, the number of the failure above that this text
shows; null when the verdict is true>}

"evidence" is a LIST because a finding often rests on more than one place in the text. Give
one entry per place, quoting only the places that decide the verdict and each of them once —
at most $max_evidence entries. Every entry must be ONE CONTINUOUS passage copied from the
text below: never join separate passages into a single entry with "..." or any other
separator — put them in separate entries instead.

Decide from the criterion's own words. A draft that partly satisfies it does not satisfy
it: answer false and quote the passages that show where it falls short.

<source>
$corpus
</source>"""
)

# --- assessment mapping (which items bear on which objective) ---------------------------
#
# Extraction, not judgement: which items measure which objective is a matter of fact about
# the two lists, so no criterion text is injected and no verdict is asked. Two criteria
# read it — one decides in code that every objective has an item, the other judges the
# matched items against the objective's declared verification.

ASSESSMENT_MAPPING_SYSTEM = """\
You analyse the assessment of educational courses. Answer with a single JSON object and
nothing else — no prose, no markdown fences. Every value described as verbatim must be
copied character-for-character from the source text."""

ASSESSMENT_MAPPING_USER = Template(
    """\
Below, between <mapping> tags, are the learning objectives a course declares and the
assessment items it ships. Each objective has an id and the outcome it promises. Each item
has an index and the question it asks.

For EACH objective, report the indices of every item that bears on it — an item that
measures what the objective promises. An objective may be measured by several items, an
item may bear on several objectives, and an objective may have none: report an empty list
rather than forcing a match.

Answer with this JSON shape, one entry per objective, in this field order:
{"objectives": [{"objectiveId": "<the objective's id, exactly as given>",
"reason": "<one sentence on what measures this objective, or that nothing does>",
"evidence": "<a passage copied verbatim from the text below: the question of one item that
bears on this objective, or the objective's own outcome when none does>",
"itemIndices": [<indices>]}]}

Exactly one entry per objective.

<mapping>
$corpus
</mapping>"""
)

# --- assessment reach (which lessons each item draws on) --------------------------------

ASSESSMENT_REACH_SYSTEM = """\
You analyse the assessment of educational courses. Answer with a single JSON object and
nothing else — no prose, no markdown fences. Every value described as verbatim must be
copied character-for-character from the source text."""

ASSESSMENT_REACH_USER = Template(
    """\
Below, between <reach> tags, is a course's lesson plan in delivery order and the
assessment items it ships. Each item names the lesson it sits in.

For EACH item, report which lessons of the plan the learner must have studied in order to
answer it — the lessons whose material the item draws on. Report the lesson identifiers
exactly as the plan gives them. An item that only tests its own lesson reports just that
lesson. Do not guess: report a lesson only when the item's question actually draws on what
that lesson covers.

This is an extraction task, not a judgement: report what the items draw on, nothing about
whether the assessment is good.

Answer with this JSON shape, one entry per item, in this field order:
{"items": [{"index": <the item's index>,
"reason": "<one sentence on what the item asks for>",
"referencesLessonIds": ["<lesson identifiers from the plan>"]}]}

Exactly one entry per item.

<reach>
$corpus
</reach>"""
)

# --- the identity fingerprint -----------------------------------------------------------

_ALL_TEMPLATES: dict[str, str] = {
    "outcomes_extraction_system": OUTCOMES_EXTRACTION_SYSTEM,
    "outcomes_extraction_user": OUTCOMES_EXTRACTION_USER.template,
    "objectives_classification_system": OBJECTIVES_CLASSIFICATION_SYSTEM,
    "objectives_classification_user": OBJECTIVES_CLASSIFICATION_USER.template,
    "concept_trajectory_system": CONCEPT_TRAJECTORY_SYSTEM,
    "concept_trajectory_user": CONCEPT_TRAJECTORY_USER.template,
    "judge_system": JUDGE_SYSTEM,
    "judge_user": JUDGE_USER.template,
    "assessment_mapping_system": ASSESSMENT_MAPPING_SYSTEM,
    "assessment_mapping_user": ASSESSMENT_MAPPING_USER.template,
    "assessment_reach_system": ASSESSMENT_REACH_SYSTEM,
    "assessment_reach_user": ASSESSMENT_REACH_USER.template,
}


def fingerprint() -> str:
    """SHA-256 over every template, in a fixed order — the part of `SOURCE_CONFIG` that
    makes a silent prompt edit visible to the ratification guard."""
    corpus = "\n\x00\n".join(f"{name}\n{text}" for name, text in sorted(_ALL_TEMPLATES.items()))
    return hashlib.sha256(corpus.encode("utf-8")).hexdigest()
