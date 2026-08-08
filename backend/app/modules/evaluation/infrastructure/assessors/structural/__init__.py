"""`structural` v1 — the first automated assessor (ADR-0016/0018/0019).

Owes itself to the `learnpack-course-qa` instrument lineage. Executes the seven
mechanically-verifiable criteria (three declaration counts — inert on LearnpackV1 until
the package declares those data — plus four structural checks over the lesson index and
activities) and abstains from the four pedagogical-judgment criteria ADR-0018 names:
judging them honestly needs semantics no pure-code executor has (an LLM-carrying
assessor may cover them later — a different artifact, a different identity).

Any change here — an executor, the mapping, an abstention — is a NEW VERSION and a new
identity (ADR-0016 clause 2); ratifying new instrument versions is not a change
(ADR-0019).
"""

from app.modules.evaluation.domain.model import Coverage
from app.modules.evaluation.infrastructure.assessors.structural import executors

NAME = "structural"
VERSION = "1"
INSTRUMENT_ID = "learnpack-course-qa"

EXECUTORS = {
    "cr-objectives-min-count": executors.objectives_min_count,
    "cr-audience-declared": executors.audience_declared,
    "cr-prerequisites-declared": executors.prerequisites_declared,
    "cr-lessons-with-activities": executors.lessons_with_activities,
    "cr-module-structure-well-formed": executors.module_structure_well_formed,
    "cr-course-opens-with-general-intro": executors.course_opens_with_general_intro,
    "cr-course-has-development": executors.course_has_development,
}

ABSTENTIONS = {
    # Criteria whose evidence is semantic. Two shapes, both out of reach of pure code: some
    # need the judgment itself (is this verb at the right cognitive level?), most need only
    # EXTRACTION or CLASSIFICATION, after which the pass condition is a count or an order
    # check. The second shape is the cheaper one an LLM-carrying assessor should take first.
    "cr-objectives-observable-verbs": "requires semantic judgment of verb phrasing",
    "cr-module-single-topic": "requires semantic judgment of topical focus",
    "cr-arc-character": "requires semantic judgment of lesson bodies",
    "cr-modules-intro-then-apply": "requires semantic judgment of in-module progression",
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
    "cr-practice-is-preceded-by-a-demonstration": (
        "requires semantic identification of demonstrations and of the skill each practice needs"
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
    "cr-scaffolding-fades-across-practice": (
        "requires semantic classification of how much each practice scaffolds"
    ),
    "cr-concepts-introduced-before-use": (
        "requires semantic extraction of where each concept is introduced and where it is used"
    ),
    # Mechanical, but no executor in this version of the assessor.
    "cr-lesson-type-matches-delivery": (
        "no executor for the declared-type/delivered-files correspondence"
    ),
    "cr-no-lesson-spikes-in-lexical-load": "no executor for the lexical-load measure",
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
