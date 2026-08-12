"""`drafts-hybrid` v2 — the `course-drafts-qa` lineage's LLM-carrying assessor.

v2 differs from v1 in sampling and nothing else: the model asks for no reasoning and the
output budget has room for an answer. v1 could not finish a run — its 2048-token budget
was spent entirely on the model's own thinking, so the semantic tasks came back empty
every time (the calibration traces recorded 2048–2325 reasoning tokens and no content).
Same prompts, same schemas, same decision constants, so the two are comparable in
everything except being able to answer; the version bump is what ADR-0016 clause 2 asks
for and what keeps a calibration from transferring across the change.


Hybrid in ADR-0016's own sense ("the hybrid is the norm"): one artifact, one identity,
and per criterion whatever mechanism the criterion needs. Seven executors are pure code —
a COPY of `drafts-structural` v1's, not an import, because shared code would tie the two
identities together. Five are semantic: an LLM extracts or classifies (outcome statements
and their verbs, Bloom levels of objectives, sophistication of the planned concepts) and
the executor decides pass/fail deterministically over what came back — the
extract-then-decide half of the abstention notes, built first because it is the cheap
half. The model supplies data, never verdicts.

It is ONE artifact rather than a separate LLM-only assessor because judgments do not
combine across assessors: the report and the fitness read the most recent judgment per
content, so a second assessor's evaluation would REPLACE the structural coverage instead
of adding to it. One artifact, one judgment, full coverage.

Identity (ADR-0034): the models, prompts, temperature, schemas and decision constants are
this assessor's identity, pinned in code and declared in `SOURCE_CONFIG` — including a
fingerprint of the prompt texts, so a prompt edited without a VERSION bump is refused at
ratification. The transport (key, base URL, backoff) is environment and re-versions
nothing. An irrecoverable LLM failure raises `AssessorExecutionError` and the evaluation
aborts whole; nothing persists.

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

from app.modules.evaluation.domain.model import Coverage
from app.modules.evaluation.infrastructure.assessors.drafts_hybrid import (
    executors,
    prompts,
    tasks,
)

NAME = "drafts-hybrid"
VERSION = "2"
INSTRUMENT_ID = "course-drafts-qa"

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
    # Whole-course semantic judgment — the expensive half of the spectrum, deliberately
    # left for a later version (or another artifact): these need the judgment itself over
    # lesson bodies, not extraction followed by a count or an order check.
    "cr-module-single-topic": "requires semantic judgment of topical focus",
    "cr-arc-character": "requires semantic judgment of lesson bodies",
    "cr-new-instruction-is-preceded-by-a-problem": (
        "requires semantic identification of new instructional material and of what motivates it"
    ),
    "cr-opening-lesson-connects-backwards": (
        "requires semantic judgment of whether the opening activates prior knowledge"
    ),
    "cr-closing-lesson-integrates": "requires semantic judgment of whether the closing integrates",
    "cr-closing-lesson-projects-forward": (
        "requires semantic judgment of whether the closing projects the learner forward"
    ),
    "cr-later-lessons-apply-earlier-concepts": (
        "requires semantic judgment of whether an earlier concept is applied in a new context"
    ),
    "cr-assessment-retrieves-earlier-taught-material": (
        "requires semantic matching of assessment items against earlier lessons"
    ),
    "cr-adjacent-pair-has-a-bridge": (
        "requires semantic judgment of whether a lesson pair states its relation"
    ),
    "cr-concepts-introduced-before-use": (
        "requires semantic extraction of where each concept is introduced and where it is used"
    ),
    "cr-every-objective-is-developed-somewhere": (
        "requires semantic matching of each declared objective against what the lessons teach"
    ),
    "cr-every-substantive-lesson-serves-an-objective": (
        "requires semantic matching of each lesson's content against the declared objectives"
    ),
    "cr-lesson-works-at-the-level-its-objective-demands": (
        "requires semantic classification of the cognitive level a lesson body works at"
    ),
    "cr-every-objective-has-an-assessment-item": (
        "requires semantic matching of assessment items against the objectives they measure"
    ),
    "cr-assessment-matches-the-declared-verification": (
        "requires semantic comparison of items against each objective's declared verification"
    ),
    "cr-skill-lessons-carry-a-worked-example": (
        "requires semantic identification of introduced skills and of worked examples"
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
        "models": {
            "outcomes_extraction": tasks.OUTCOMES_EXTRACTION_MODEL,
            "objectives_classification": tasks.OBJECTIVES_CLASSIFICATION_MODEL,
            "concept_trajectory": tasks.CONCEPT_TRAJECTORY_MODEL,
        },
        "promptsFingerprint": prompts.fingerprint(),
    },
}
