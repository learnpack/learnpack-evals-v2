import { assessorLabel } from "@/components/admin/assessor-label";
import type {
  CriterionOutcomeCell,
  CriterionOutcomes,
  InstrumentResponse,
  OutcomeTally,
  ReportBody,
  StudyReportGeneratorClaim,
} from "@/lib/api/types";

/** The aggregations layer 0 is made of — pure, and deliberately small.
 *
 * One rule governs all of them: **nothing is ever summed across criteria or across claims.**
 * ADR-0011 retired the single aggregate score, and a rollup is exactly where one would creep
 * back in. Every row here carries its own denominator and stops there.
 */

export interface CriterionRow {
  criterionId: string;
  /** The instrument's own words. Null when the pinned version does not declare one — the
   *  id is then all there is, and the row says so rather than inventing a sentence. */
  statement: string | null;
  passCondition: string | null;
  failureModes: string[];
  failed: number;
  /** How many courses produced ANY outcome for this criterion — the honest denominator for
   *  "failed in N of M", which is not the size of the dataset when some course went
   *  unjudged. */
  assessed: number;
  /** The dataset, for the reader who wants to know what is missing rather than what failed. */
  inDataset: number;
  distribution: Record<OutcomeTally, number>;
  cells: CriterionOutcomeCell[];
  exemplar: CriterionOutcomeCell | null;
}

export interface ClaimRow extends StudyReportGeneratorClaim {
  generatorLabel: string;
}

/** Criteria worth acting on first: most failures, then the widest coverage behind them.
 *
 * A criterion nothing assessed sorts last rather than being dropped — "nobody could judge
 * this" is a finding about the instrument or the format, and hiding it is how a gap stays
 * invisible for a whole round.
 */
export function rankCriteria(
  outcomes: CriterionOutcomes,
  instrument: InstrumentResponse | undefined,
): CriterionRow[] {
  const declared = new Map((instrument?.criteria ?? []).map((c) => [c.criterion_id, c]));

  return outcomes.criteria
    .map((section) => {
      const spec = declared.get(section.criterionId);
      const failing = section.outcomes.filter((cell) => cell.outcome === "fail");
      return {
        criterionId: section.criterionId,
        statement: spec?.statement ?? null,
        passCondition: spec?.pass_condition ?? null,
        failureModes: spec?.failure_modes ?? [],
        failed: section.distribution.fail,
        assessed: section.coverage.observed,
        inDataset: section.coverage.of,
        distribution: section.distribution,
        cells: section.outcomes,
        // The first failure that quoted something: a row with a passage under it is worth
        // more than a row with a number, and one of them is free.
        exemplar: failing.find((cell) => cell.quote !== null) ?? failing[0] ?? null,
      };
    })
    .sort((a, b) => b.failed - a.failed || b.assessed - a.assessed ||
      a.criterionId.localeCompare(b.criterionId));
}

/** Claims worth acting on first: most refuted, then most insufficient.
 *
 * Insufficient breaks the tie rather than being ignored, because it is a different problem
 * with the same urgency — a claim nobody could evidence is a hole in the argument, not a
 * quiet pass.
 */
export function rankClaims(body: ReportBody): ClaimRow[] {
  return body.generatorLevel
    .flatMap((generator) =>
      generator.perClaim.map((claim) => ({
        ...claim,
        generatorLabel: generator.name
          ? `${generator.name}${generator.version ? ` ${generator.version}` : ""}`
          : generator.generatorVersionId,
      })),
    )
    .sort(
      (a, b) =>
        (b.distribution.refuted ?? 0) - (a.distribution.refuted ?? 0) ||
        (b.distribution.insufficient ?? 0) - (a.distribution.insufficient ?? 0) ||
        a.claimId.localeCompare(b.claimId),
    );
}

export interface CourseCriterionRow {
  criterionId: string;
  statement: string | null;
  cell: CriterionOutcomeCell;
}

/** Every criterion of one course, in the instrument's own order — layer 2's index.
 *
 * A criterion this course produced no outcome for is left out rather than shown empty: at
 * the whole-dataset grain a missing cell is a coverage fact worth a row, but on one course
 * it is just noise, and the criterion's own row upstairs already counts it.
 */
export function byCourse(
  outcomes: CriterionOutcomes,
  instrument: InstrumentResponse | undefined,
  contentId: string,
): CourseCriterionRow[] {
  const declared = new Map((instrument?.criteria ?? []).map((c) => [c.criterion_id, c]));
  const rows: CourseCriterionRow[] = [];
  for (const section of outcomes.criteria) {
    const cell = section.outcomes.find((c) => c.contentId === contentId);
    if (cell) {
      rows.push({
        criterionId: section.criterionId,
        statement: declared.get(section.criterionId)?.statement ?? null,
        cell,
      });
    }
  }
  return rows;
}

export interface CaveatRow {
  key: string;
  label: string;
  detail: string;
  /** False when the caveat has nothing to report — the row still exists, because "we
   *  checked and there was none" is information and an absent row is not. */
  raised: boolean;
}

/** The caveat kinds as rows, each one saying whether it fired.
 *
 * Publishing with caveats is legitimate and visible; publishing silently is impossible
 * (12-define invariant 4). So none of them may be dropped — but a screenful of "none" at
 * the top of a report is how a reader learns to skip the section that exists to stop them
 * skipping it. They collapse behind one line instead.
 *
 * Kinds added after a report was frozen are absent from it, not empty, and each such row
 * reads its field defensively: a report published at an older schema version is the record
 * it is, and rendering it must not depend on fields nobody could have written.
 */
export function caveatRows(body: ReportBody): CaveatRow[] {
  const c = body.caveats;
  const executionErrors = c.executionErrors?.perContent ?? [];
  const errored = executionErrors.reduce((sum, entry) => sum + entry.count, 0);
  const mixed = c.mixedAssessors?.assessors ?? [];

  return [
    {
      key: "insufficientEvidence",
      label: "Insufficient evidence",
      detail: c.insufficientEvidence.length
        ? `${c.insufficientEvidence.length} claim-and-course pairs could not be decided`
        : "every claim reached a verdict",
      raised: c.insufficientEvidence.length > 0,
    },
    {
      key: "contentsWithoutJudgment",
      label: "Courses with no judgment",
      detail: c.contentsWithoutJudgment.length
        ? `${c.contentsWithoutJudgment.length} of ${body.dataset.size} carry none`
        : "every course was judged",
      raised: c.contentsWithoutJudgment.length > 0,
    },
    {
      key: "executionErrors",
      label: "Criteria the run could not judge",
      detail: errored
        ? `${errored} across ${executionErrors.length} course(s) — a failure of this run, not of the course`
        : "none",
      raised: errored > 0,
    },
    {
      key: "unknownExclusions",
      label: "Unknown-generator exclusions",
      detail: c.unknownExclusions.contentIds.length
        ? `${c.unknownExclusions.contentIds.length} course(s) left out of generator-level counting — attributable later`
        : "every course names its generator",
      raised: c.unknownExclusions.contentIds.length > 0,
    },
    {
      key: "unacceptedAdapters",
      label: "Unaccepted adapters",
      detail: c.unacceptedAdapters.length
        ? c.unacceptedAdapters
            .map((a) => `${a.packageFormat} (${a.adapterVersion ?? "no adapter"})`)
            .join(" · ")
        : "every format's extraction is accepted",
      raised: c.unacceptedAdapters.length > 0,
    },
    {
      key: "briefCompleteness",
      label: "Incomplete briefs",
      detail: c.briefCompleteness.length
        ? `${c.briefCompleteness.length} commission(s) with no prompt recorded`
        : "every brief records its prompt",
      raised: c.briefCompleteness.length > 0,
    },
    {
      key: "mixedAssessors",
      label: "More than one judge",
      detail: mixed.length
        ? `${mixed.map(assessorLabel).join(" · ")} — every distribution below pools courses judged by different artifacts`
        : "one assessor produced every judgment",
      raised: mixed.length > 0,
    },
    {
      key: "unresolvedDisagreements",
      label: "Unresolved disagreements",
      detail: c.unresolvedDisagreements.length
        ? `${c.unresolvedDisagreements.length}`
        : "none — a single automated assessor cannot disagree with itself",
      raised: c.unresolvedDisagreements.length > 0,
    },
    {
      key: "taskVariablePatterns",
      label: "Task-variable patterns",
      detail: `${c.taskVariablePatterns.status}: ${c.taskVariablePatterns.reason}`,
      raised: false,
    },
  ];
}
