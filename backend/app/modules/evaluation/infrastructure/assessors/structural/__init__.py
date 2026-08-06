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
    "cr-objectives-observable-verbs": "requires semantic judgment of verb phrasing",
    "cr-module-single-topic": "requires semantic judgment of topical focus",
    "cr-arc-character": "requires semantic judgment of lesson bodies",
    "cr-modules-intro-then-apply": "requires semantic judgment of in-module progression",
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
