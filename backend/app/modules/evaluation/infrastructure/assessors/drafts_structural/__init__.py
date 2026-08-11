"""`drafts-structural` v1 — the first assessor of the `course-drafts-qa` lineage.

Owes itself to `course-drafts-qa` (ADR-0019: an assessor vouches for one argument, so the
lineage that finally has an artifact declared against it can finally ratify). Coverage is
declared over the 29 criteria of v2, a superset of v1's 22 — ratification requires the
coverage to decide every criterion of the target version, so both published versions of
the lineage can be ratified by this one artifact.

A COPY of `structural` v1 restricted to this lineage's criteria, not an import: ADR-0016
gives an algorithm its identity through the assessor's version, and shared code would tie
the two identities together. The one behavioural difference is deliberate — the objectives
count metric is `declared_objectives_count`, because this lineage mints a data requirement
named `declared_objectives` (the objectives themselves) and a report must not carry one
name with two meanings (see `executors.objectives_min_count`).

Executes the seven mechanically-verifiable criteria and abstains from the rest: judging
them honestly needs semantics no pure-code executor has (an LLM-carrying assessor may
cover them later — a different artifact, a different identity). `cr-prerequisites-declared`
is declared executed even though LearnpackV2 supplies no `prerequisites` capability —
coverage states the lineage's demand this artifact can realize, not any one format's
supply, and the unmet demand derives `not_applicable` before the executor runs.

One of the seven reads a measure rather than a structure: `lexical_load`, in `measures.py`.
Its algorithm is part of THIS assessor's identity, so changing it is a new version even
though no criterion's wording moves.

Any change here — an executor, the mapping, an abstention — is a NEW VERSION and a new
identity (ADR-0016 clause 2); ratifying new instrument versions is not a change
(ADR-0019).
"""

from app.modules.evaluation.domain.model import Coverage
from app.modules.evaluation.infrastructure.assessors.drafts_structural import executors

NAME = "drafts-structural"
VERSION = "1"
INSTRUMENT_ID = "course-drafts-qa"

EXECUTORS = {
    "cr-objectives-min-count": executors.objectives_min_count,
    "cr-audience-declared": executors.audience_declared,
    "cr-prerequisites-declared": executors.prerequisites_declared,
    "cr-module-structure-well-formed": executors.module_structure_well_formed,
    "cr-course-opens-with-general-intro": executors.course_opens_with_general_intro,
    "cr-course-has-development": executors.course_has_development,
    "cr-no-lesson-spikes-in-lexical-load": executors.no_lesson_spikes_in_lexical_load,
}

ABSTENTIONS = {
    # Criteria whose evidence is semantic. Two shapes, both out of reach of pure code: some
    # need the judgment itself (is this verb at the right cognitive level?), most need only
    # EXTRACTION or CLASSIFICATION, after which the pass condition is a count or an order
    # check. The second shape is the cheaper one an LLM-carrying assessor should take first.
    "cr-objectives-observable-verbs": "requires semantic judgment of verb phrasing",
    "cr-module-single-topic": "requires semantic judgment of topical focus",
    "cr-arc-character": "requires semantic judgment of lesson bodies",
    "cr-outcomes-present": "requires semantic extraction of the outcomes the opening lesson states",
    "cr-outcomes-observable-verbs": (
        "requires semantic extraction of the stated outcomes and their verbs"
    ),
    "cr-objectives-verb-level-band": (
        "requires semantic judgment of cognitive level against the declared difficulty"
    ),
    "cr-objectives-non-decreasing-demand": (
        "requires semantic classification of each objective's cognitive level"
    ),
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
    # The seven criteria v2 added — the constructive-alignment dimension and the two
    # returning qualities. All semantic by design (the instrument says so): they document
    # the demand the LLM-carrying assessor will find waiting.
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
    "cr-cognitive-demand-rises-across-the-course": (
        "requires semantic classification of each concept's sophistication along the sequence"
    ),
}

# Derived from the executor dict itself — no parallel list to drift (plan review note).
COVERAGE = Coverage(executes=frozenset(EXECUTORS), abstains=ABSTENTIONS)

SOURCE_CONFIG = {
    "name": NAME,
    "version": VERSION,
    "instrumentId": INSTRUMENT_ID,
    "coverage": {
        "executes": sorted(EXECUTORS),
        "abstains": dict(sorted(ABSTENTIONS.items())),
    },
}
