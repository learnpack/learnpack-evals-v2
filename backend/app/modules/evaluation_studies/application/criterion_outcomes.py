"""The per-criterion record across a study's dataset — pure, over local DTOs.

Read-only and composed on read, like the fitness projection and for its reason (ADR-0023):
it must not travel inside `study_reports.report`, whose jsonb is frozen when the study is
signed off and corrected never. Two things the report structurally cannot say, and this
exists to say them:

* **The evidence of a pass.** Findings are minted one per FAILING criterion, so the quote
  that grounds a pass — persisted for every pass, guaranteed by a CHECK constraint — is
  otherwise readable nowhere. Here every cell carries its own evidence, whatever state it
  is in.
* **A denominator.** "Which check fails most across these twenty courses" cannot be
  answered by counting findings, and a count with no denominator is what ADR-0011 forbids.
  So the criteria come from the INSTRUMENT and never from the outcomes that happen to
  exist, every distribution travels with its coverage (ADR-0011 clause 3), and nothing is
  ever summed across criteria — a cross-criterion total is the aggregate score that ADR
  retired.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.evaluation_studies.application.dtos import (
    ContentInfo,
    CriterionOutcomeInfo,
    InstrumentInfo,
    JudgmentInfo,
)
from app.modules.evaluation_studies.application.report import assessors_used, latest_judgments
from app.modules.evaluation_studies.domain.model import Study

# The same camelCase vocabulary `evidence_basis` uses. Spelled again here rather than
# imported from the fitness projection: that module owns a PARTITION of these states into
# numerator, penalizing and excluded, which is an optimization choice — and a document a QA
# reader opens must not acquire it by proximity.
STATE_KEYS = {
    "pass": "pass",
    "fail": "fail",
    "no_evidence": "noEvidence",
    "not_applicable": "notApplicable",
    "not_assessed": "notAssessed",
    "execution_error": "executionError",
}

JUDGMENT_BASIS_NOTE = {
    "signedOffReport": (
        "the judgments this study's frozen report recorded — re-evaluating a course after "
        "signing off does not rewrite what that report reflects"
    ),
    "current": (
        "the most recent judgment per course: this study has frozen no report yet, so there "
        "is nothing else this could mean"
    ),
}


def _judgments_in_view(
    judgments: list[JudgmentInfo], frozen_report: dict[str, Any] | None
) -> tuple[str, dict[UUID, JudgmentInfo]]:
    """Which judgment each course is read through — the one correctness rule here.

    The most recent one is right only while nothing has been frozen. Once a report exists
    it decides: it named its judgments and it is immutable, so reading "the latest" against
    a signed-off study would show evidence for a document that never saw it. An EMPTY set of
    recorded judgments means exactly what it says — that report reflects none — and is
    honoured rather than fallen back from.
    """
    if frozen_report is None:
        return "current", latest_judgments(judgments)

    by_id = {judgment.judgment_id: judgment for judgment in judgments}
    view: dict[UUID, JudgmentInfo] = {}
    for content_id, judgment_id in (frozen_report.get("judgmentIdsUsed") or {}).items():
        judgment = by_id.get(UUID(judgment_id))
        if judgment is not None:
            view[UUID(content_id)] = judgment
    return "signedOffReport", view


def _cell(outcome: CriterionOutcomeInfo) -> dict[str, Any]:
    """One criterion under one course, with the evidence the row already carries.

    `quote` is present for every pass and every non-derived fail; it is null exactly where
    the CHECK constraints permit — an absence-derived fail (ADR-0021) or an execution error
    (ADR-0037) — and both of those name their own cause instead.
    """
    return {
        "contentId": str(outcome.content_id),
        "outcome": outcome.outcome,
        "derived": outcome.derived,
        "quote": outcome.quote,
        "locator": outcome.locator,
        "failureMode": outcome.failure_mode,
        "comment": outcome.comment,
        "executionCause": outcome.execution_cause,
    }


def compute_criterion_outcomes(
    study: Study,
    instrument: InstrumentInfo | None,
    contents: list[ContentInfo],
    judgments: list[JudgmentInfo],
    outcomes: list[CriterionOutcomeInfo],
    frozen_report: dict[str, Any] | None,
    computed_at: datetime,
) -> dict[str, Any]:
    """One section per criterion the instrument declares, over the whole dataset.

    Criterion-major because that is the question being asked: a criterion is the unit that
    passes or fails across twenty courses, and its denominator is the dataset. The courses
    are named ONCE in a header table and the cells carry only the id — eight hundred
    repetitions of a label is not a reading.
    """
    gaps: list[dict[str, Any]] = []
    if study.instrument_version_id is None:
        gaps.append({"gap": "instrument_not_chosen"})
    if study.assessor_id is None:
        # ADR-0042 §9: with no judge, this document is composed from every judgment on the
        # dataset whoever produced it. Saying so is the difference between a reader who
        # knows what they are holding and one who assumes.
        gaps.append({"gap": "assessor_not_chosen"})
    if not study.content_ids:
        gaps.append({"gap": "dataset_not_composed"})
    if study.instrument_version_id is not None and instrument is None:
        # Distinct from "not chosen": a chosen version that cannot be read is a real fault.
        gaps.append({"gap": "instrument_not_found"})

    basis, current = _judgments_in_view(judgments, frozen_report)

    header: dict[str, Any] = {
        "studyId": str(study.id),
        "status": study.status,
        "instrumentVersionId": study.instrument_version_id,
        "computedAt": computed_at.isoformat(),
        # Said in the payload, not only in the docs: un-aggregated evidence with its own
        # denominator, never a score — ADR-0011 retired the cross-criterion total.
        "signal": "evidence",
        "judgmentBasis": {"basis": basis, "note": JUDGMENT_BASIS_NOTE[basis]},
        # Whose evidence this is (ADR-0042). It belongs beside `judgmentBasis` because the
        # two answer the same shape of question — which judgments am I looking at, and
        # whose — and a cell's quote means nothing without the second half.
        "assessorsUsed": assessors_used(current),
        "gaps": gaps,
    }
    if instrument is None:
        return header | {"contents": [], "criteria": [], "contentsWithoutJudgment": []}

    observed: dict[str, dict[UUID, CriterionOutcomeInfo]] = {}
    for outcome in outcomes:
        judgment = current.get(outcome.content_id)
        # Only the outcomes of the judgment IN VIEW: judgments are append-only, and a
        # superseded one must not sit beside the one the study is being read through.
        if judgment is None or judgment.judgment_id != outcome.judgment_id:
            continue
        observed.setdefault(outcome.criterion_id, {})[outcome.content_id] = outcome

    content_table: list[dict[str, Any]] = []
    for content in sorted(contents, key=lambda c: str(c.content_id)):
        judgment = current.get(content.content_id)
        content_table.append(
            {
                "contentId": str(content.content_id),
                "externalId": content.external_id,
                "briefId": str(content.brief_id) if content.brief_id else None,
                "generatorVersionId": (
                    str(content.generator_version_id) if content.generator_version_id else None
                ),
                "judgmentId": str(judgment.judgment_id) if judgment else None,
                "derivedAt": judgment.derived_at.isoformat() if judgment else None,
            }
        )

    criteria_sections: list[dict[str, Any]] = []
    for criterion in instrument.criteria:
        cells = observed.get(criterion.criterion_id, {})
        distribution = {key: 0 for key in STATE_KEYS.values()}
        rows: list[dict[str, Any]] = []
        for _, outcome in sorted(cells.items(), key=lambda kv: str(kv[0])):
            key = STATE_KEYS.get(outcome.outcome)
            if key is None:
                # Loud, never silent: a state this vocabulary does not name would vanish
                # from the distribution while still sitting inside the coverage, which is
                # the arithmetic that lies. The six are CHECK-constrained, so this can only
                # fire when the constraint moved and the code did not.
                raise ValueError(
                    f"unknown outcome state {outcome.outcome!r} — the matrix must name "
                    "every state the database admits"
                )
            distribution[key] += 1
            rows.append(_cell(outcome))
        criteria_sections.append(
            {
                "criterionId": criterion.criterion_id,
                # From the instrument, never from the judgment: a claim excluded by
                # coverage has no row there at all.
                "claimIds": list(criterion.claim_ids),
                "distribution": distribution,
                # Coverage alongside every distribution (ADR-0011 clause 3), and the
                # denominator is the DATASET: a criterion nothing produced an outcome for
                # reads `0 of 20` rather than a missing row nobody would miss.
                "coverage": {"observed": len(cells), "of": len(contents)},
                "outcomes": rows,
            }
        )

    return header | {
        "contents": content_table,
        "criteria": criteria_sections,
        # The same name the report's caveats give the same fact.
        "contentsWithoutJudgment": [
            str(c.content_id) for c in contents if c.content_id not in current
        ],
    }
