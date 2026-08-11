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

# --- the identity fingerprint -----------------------------------------------------------

_ALL_TEMPLATES: dict[str, str] = {
    "outcomes_extraction_system": OUTCOMES_EXTRACTION_SYSTEM,
    "outcomes_extraction_user": OUTCOMES_EXTRACTION_USER.template,
    "objectives_classification_system": OBJECTIVES_CLASSIFICATION_SYSTEM,
    "objectives_classification_user": OBJECTIVES_CLASSIFICATION_USER.template,
    "concept_trajectory_system": CONCEPT_TRAJECTORY_SYSTEM,
    "concept_trajectory_user": CONCEPT_TRAJECTORY_USER.template,
}


def fingerprint() -> str:
    """SHA-256 over every template, in a fixed order — the part of `SOURCE_CONFIG` that
    makes a silent prompt edit visible to the ratification guard."""
    corpus = "\n\x00\n".join(f"{name}\n{text}" for name, text in sorted(_ALL_TEMPLATES.items()))
    return hashlib.sha256(corpus.encode("utf-8")).hexdigest()
