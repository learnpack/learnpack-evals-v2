"""The fitness projection — pure, over local DTOs (ADR-0023).

A **read-side signal for optimization, never a judgment**. It is the fitness function of the
genetic-algorithm experiment (individual = `GeneratorVersion`, generation = `Study`), and it
deliberately stays out of `StudyReport`: ADR-0011 forbids an aggregate score in the product,
and this number escapes those reasons only for a consumer that needs a gradient rather than a
meaning.

Everything here is arithmetic over what the caller already gathered — no I/O, no clock. The
one rule worth reading twice is the denominator (§2 of the ADR): `no_evidence` and the
absence-derived `fail` are the generator's omissions and must penalize, or evolution learns
that the cheapest way to score well is to produce unevaluable content; `not_assessed` is our
tooling's limit, `not_applicable` is unmet demand and `execution_error` is this run's own
failure (ADR-0037), so none of them is charged to the generator.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.evaluation_studies.application.dtos import (
    BriefInfo,
    ContentInfo,
    CriterionOutcomeInfo,
    GeneratorInfo,
    InstrumentInfo,
    JudgmentInfo,
    RatificationInfo,
)
from app.modules.evaluation_studies.application.report import assessors_used, latest_judgments
from app.modules.evaluation_studies.domain.model import Study

# Bump when the arithmetic changes: values carrying different versions are not comparable,
# which is the whole point of pinning it (ADR-0023 §9).
FITNESS_FORMULA_VERSION = "1"

PASSED = "pass"
# In the denominator and penalizing — the generator's own omissions.
PENALIZED = ("fail", "no_evidence")
# Out of the denominator — an assessor limitation, unmet demand and this run's execution
# failures: none of them the generator's fault (ADR-0023 §2, ADR-0037 §6).
EXCLUDED = ("not_applicable", "not_assessed", "execution_error")

# camelCase state names, the same vocabulary `evidence_basis` uses.
STATE_KEYS = {
    "pass": "pass",
    "fail": "fail",
    "no_evidence": "noEvidence",
    "not_applicable": "notApplicable",
    "not_assessed": "notAssessed",
    "execution_error": "executionError",
}

# Declared in the payload so nobody has to reverse-engineer the number from a value.
DENOMINATOR_RULE = {
    "numerator": [PASSED],
    "penalizing": list(PENALIZED),
    "excluded": list(EXCLUDED),
    "note": (
        "Optimization denominator, not the QA one: ADR-0018 keeps not_assessed inside the "
        "coverage denominator of a judgment, this drops it. Same state, two purposes. "
        "execution_error is likewise out (a failure of our run, not of the generator) and "
        "extends the §7 equal-coverage rule to execution variance: two runs of the same "
        "content are comparable only where their executionError counts permit (ADR-0037 §6). "
        "The formula version stays 1: the state could not exist in rows persisted before "
        "ADR-0037, so no already-computed value changes."
    ),
}


def criteria_by_quality(instrument: InstrumentInfo) -> dict[str, frozenset[str]]:
    """`quality → the criteria that evidence any claim asserting about it`.

    Criteria never reference qualities; the claim mediates (12-define). A **set** is what
    makes the traversal safe: a criterion evidencing two claims of the same quality counts
    once, structurally rather than by a special rule. Across *different* qualities a
    criterion does count fully in each — splitting would make its weight depend on how many
    qualities its claim happens to mention (ADR-0023 §4).
    """
    claims_of_quality: dict[str, set[str]] = {}
    for claim in instrument.claims:
        for quality_id in claim.quality_ids:
            claims_of_quality.setdefault(quality_id, set()).add(claim.claim_id)

    result: dict[str, frozenset[str]] = {}
    for quality_id, claim_ids in claims_of_quality.items():
        result[quality_id] = frozenset(
            criterion.criterion_id
            for criterion in instrument.criteria
            if claim_ids.intersection(criterion.claim_ids)
        )
    return result


def _tally(outcomes: list[str]) -> dict[str, int]:
    counts = {key: 0 for key in STATE_KEYS.values()}
    for outcome in outcomes:
        key = STATE_KEYS.get(outcome)
        if key is None:
            # Loud, never silent: a state this partition does not name would otherwise
            # vanish from the counts and the coverage — the NaN failure mode (ADR-0037 §6).
            raise ValueError(
                f"unknown outcome state {outcome!r} — the fitness partition must name "
                "every state (ADR-0037 §6)"
            )
        counts[key] += 1
    return counts


def _denominator(counts: dict[str, int]) -> int:
    return counts["pass"] + sum(counts[STATE_KEYS[state]] for state in PENALIZED)


def _score(counts: dict[str, int]) -> float | None:
    """`pass / (pass + fail + noEvidence)`, or **undefined** when nothing was measurable.

    Never zero: zero asserts that everything measurable failed, when nothing was measurable
    (ADR-0023 §6).
    """
    denominator = _denominator(counts)
    if denominator == 0:
        return None
    return round(counts["pass"] / denominator, 6)


def _quality_section(counts: dict[str, int], dimension_id: str | None) -> dict[str, Any]:
    return {
        "fitness": _score(counts),
        "dimensionId": dimension_id,
        "coverage": {
            "criteria": sum(counts.values()),
            "denominator": _denominator(counts),
            **counts,
        },
    }


def _roll_up(
    qualities: dict[str, dict[str, Any]], quality_dimensions: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """A dimension is the **unweighted mean** of its defined qualities (ADR-0023 §5).

    Not a sum — a sum would grow with how many qualities an instrument happens to cover, so
    two instrument versions would stop being comparable. Undefined qualities are left out of
    the mean rather than read as zero, and a dimension with none is itself undefined.
    """
    dimensions: dict[str, dict[str, Any]] = {}
    for quality_id, section in qualities.items():
        dimension_id = quality_dimensions.get(quality_id)
        if dimension_id is None:  # a quality that groups nowhere rolls up nowhere
            continue
        entry = dimensions.setdefault(dimension_id, {"scores": [], "qualities": 0})
        entry["qualities"] += 1
        if section["fitness"] is not None:
            entry["scores"].append(section["fitness"])

    return {
        dimension_id: {
            "fitness": (
                round(sum(entry["scores"]) / len(entry["scores"]), 6) if entry["scores"] else None
            ),
            "coverage": {"qualities": entry["qualities"], "defined": len(entry["scores"])},
        }
        for dimension_id, entry in dimensions.items()
    }


def _level(
    outcomes_by_criterion: dict[str, list[str]],
    quality_criteria: dict[str, frozenset[str]],
    quality_dimensions: dict[str, str],
) -> dict[str, Any]:
    """One grain's whole picture: every quality the instrument measures, then the roll-up.

    `outcomes_by_criterion` pools however many contents this grain covers — pooling, not a
    mean of means, because contents are samples of one population (ADR-0023 §5).
    """
    qualities = {
        quality_id: _quality_section(
            _tally(
                [
                    o
                    for criterion_id in criteria
                    for o in outcomes_by_criterion.get(criterion_id, [])
                ]
            ),
            quality_dimensions.get(quality_id),
        )
        for quality_id, criteria in quality_criteria.items()
    }
    return {
        "qualities": {q: qualities[q] for q in sorted(qualities)},
        "dimensions": dict(sorted(_roll_up(qualities, quality_dimensions).items())),
    }


def _brief_table(
    study: Study, contents: list[ContentInfo], briefs: dict[UUID, BriefInfo]
) -> list[dict[str, Any]]:
    """The commissions this study was computed over — one entry each, never per content.

    The recipe **union** what the contents reference, so a brief that produced no course (a
    generation that failed) is read as an empty group instead of disappearing. The hash rides
    along because the id is minted per store and the hash is not: it is what keeps a series
    joinable across a rebuilt database (ADR-0039 §3–§4).
    """
    wanted = set(study.brief_ids) | {c.brief_id for c in contents if c.brief_id is not None}
    table: list[dict[str, Any]] = []
    for brief_id in sorted(wanted, key=str):
        brief = briefs.get(brief_id)
        # A brief the caller could not read is still named: dropping the row would take the
        # group with it, and a group of courses is what this table exists to identify.
        table.append(
            {
                "briefId": str(brief_id),
                "briefHash": brief.brief_hash if brief is not None else None,
                "brief": brief.brief if brief is not None else None,
            }
        )
    return table


def compute_fitness(
    study: Study,
    instrument: InstrumentInfo | None,
    contents: list[ContentInfo],
    briefs: dict[UUID, BriefInfo],
    generators: dict[UUID, GeneratorInfo],
    judgments: list[JudgmentInfo],
    outcomes: list[CriterionOutcomeInfo],
    ratifications: list[RatificationInfo],
    computed_at: datetime,
) -> dict[str, Any]:
    """The projection over a study, at three grains: content, generator version, study.

    Coverage travels with every value and the ratified assessors are named, because dropping
    `not_assessed` means two assessor sets produce values over *different populations*: the
    GA may only compare within equal coverage, and that has to be checkable (ADR-0023 §7).

    The **brief is a fourth axis and not a fourth grain** (ADR-0039): each content carries the
    commission it answers, the header names the commissions, and nothing is pooled per brief —
    a consumer can derive a pooled value from labelled contents, but nobody can recover from a
    pooled value how much the courses of one commission differed, which is what the repeats
    exist to measure.
    """
    gaps: list[dict[str, Any]] = []
    if study.instrument_version_id is None:
        gaps.append({"gap": "instrument_not_pinned"})
    if not study.content_ids:
        gaps.append({"gap": "dataset_not_composed"})
    if study.instrument_version_id is not None and instrument is None:
        # Distinct from "not pinned": a pinned version that cannot be read is a real fault.
        gaps.append({"gap": "instrument_not_found"})

    header: dict[str, Any] = {
        "studyId": str(study.id),
        "status": study.status,
        "instrumentVersionId": study.instrument_version_id,
        "formulaVersion": FITNESS_FORMULA_VERSION,
        "computedAt": computed_at.isoformat(),
        # Said in the payload, not only in the docs: this is a gradient, not a verdict, and
        # no aggregate score of this kind belongs in a QA report (ADR-0011).
        "signal": "optimization",
        "denominatorRule": DENOMINATOR_RULE,
        "gaps": gaps,
        # The grouping axis, named once (ADR-0039 §3): contents carry the id, this says which
        # commission each id is. In the header so it answers at any status, like the gaps.
        "briefs": _brief_table(study, contents, briefs),
    }
    if instrument is None:
        return header | {"assessorCoverage": {}, "contents": [], "generators": [], "study": {}}

    quality_criteria = criteria_by_quality(instrument)
    quality_dimensions = instrument.quality_dimensions
    current = latest_judgments(judgments)
    used = {judgment.judgment_id for judgment in current.values()}

    # Only the outcomes of the CURRENT judgment per content: judgments are append-only, and
    # a superseded one must not contribute to the number the GA reads.
    per_content: dict[UUID, dict[str, list[str]]] = {}
    for outcome in outcomes:
        if outcome.judgment_id not in used:
            continue
        per_content.setdefault(outcome.content_id, {}).setdefault(outcome.criterion_id, []).append(
            outcome.outcome
        )

    content_sections: list[dict[str, Any]] = []
    pooled_by_generator: dict[UUID, dict[str, list[str]]] = {}
    contents_by_generator: dict[UUID, int] = {}
    study_pool: dict[str, list[str]] = {}
    unknown_exclusions: list[str] = []

    for content in sorted(contents, key=lambda c: str(c.content_id)):
        judged = per_content.get(content.content_id, {})
        content_sections.append(
            {
                "contentId": str(content.content_id),
                "externalId": content.external_id,
                # The commission this course answers, `null` when the intake derived none
                # (ADR-0022 §4) — an absent brief groups nowhere and is reported as itself.
                "briefId": str(content.brief_id) if content.brief_id else None,
                "generatorVersionId": (
                    str(content.generator_version_id) if content.generator_version_id else None
                ),
                "judged": bool(judged),
                **_level(judged, quality_criteria, quality_dimensions),
            }
        )
        for criterion_id, states in judged.items():
            study_pool.setdefault(criterion_id, []).extend(states)

        if content.generator_version_id is None:
            # Declared unknown (ADR-0024): valid per content, out of generator accumulation.
            unknown_exclusions.append(str(content.content_id))
            continue
        contents_by_generator[content.generator_version_id] = (
            contents_by_generator.get(content.generator_version_id, 0) + 1
        )
        pool = pooled_by_generator.setdefault(content.generator_version_id, {})
        for criterion_id, states in judged.items():
            pool.setdefault(criterion_id, []).extend(states)

    generator_sections = []
    for generator_id in sorted(pooled_by_generator, key=str):
        generator = generators.get(generator_id)
        generator_sections.append(
            {
                "generatorVersionId": str(generator_id),
                "name": generator.name if generator else None,
                "version": generator.version if generator else None,
                "contents": contents_by_generator[generator_id],
                **_level(pooled_by_generator[generator_id], quality_criteria, quality_dimensions),
            }
        )

    not_assessed = sum(
        1 for states in study_pool.values() for state in states if state == "not_assessed"
    )
    execution_errors = sum(
        1 for states in study_pool.values() for state in states if state == "execution_error"
    )
    return header | {
        "assessorCoverage": {
            # Two lists that answer two different questions, and the difference is the
            # point (ADR-0042). `ratifiedAssessors` is scoped to the INSTRUMENT VERSION —
            # who was permitted to judge with it, anywhere. `assessorsUsed` is scoped to
            # THIS study — who actually produced the judgments these values are computed
            # from. More than one entry there means the numbers pool populations judged by
            # different artifacts, which is exactly the comparison the note forbids.
            "ratifiedAssessors": sorted(str(r.assessor_id) for r in ratifications),
            "assessorsUsed": assessors_used(current),
            "notAssessed": not_assessed,
            "executionErrors": execution_errors,
            "note": (
                "Values computed under different assessor coverage are not comparable: "
                "not_assessed is outside the denominator, so the population differs. "
                "executionErrors differ between runs of the SAME content under the SAME "
                "assessor — compare only where these counts permit (ADR-0037 §6). "
                "ratifiedAssessors names who MAY judge with this instrument version; "
                "assessorsUsed names who DID judge this study, and more than one there "
                "means these values pool more than one judge."
            ),
        },
        "contents": content_sections,
        "generators": generator_sections,
        "unknownExclusions": unknown_exclusions,
        "study": _level(study_pool, quality_criteria, quality_dimensions),
    }
