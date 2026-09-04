import type { CampaignReport, CampaignReportContent, CampaignReportItem } from "@/lib/api/types";

/** The orderings and the roll-ups the campaign report reads by — pure, and deliberately
 *  small.
 *
 *  Ranking lives here rather than in component state because the order is an argument, not a
 *  preference: ADR-0060 §2 says the first question is *which items are answerable*, and a
 *  screen that opens alphabetically makes the reader find that out for themselves.
 *
 *  One rule governs everything below, ADR-0011's: nothing is ever summed across items. Every
 *  row carries its own denominator and stops there.
 */

export interface RankedItem extends CampaignReportItem {
  /** Courses where somebody was asked at all — this row's honest denominator. It is not the
   *  size of the scope: four of the twelve items rest on a declaration many courses do not
   *  make (ADR-0052's accepted cost). */
  askedContents: number;
}

/** Items worst-agreement first, then most-contested, then by the instrument's own order.
 *
 * An item with no pair at all sorts **last** rather than first: "nobody could be compared on
 * this" is a fact about the campaign's progress or about the item's dependence on a
 * declaration, and it does not belong at the top of a list whose subject is disagreement.
 */
export function rankItems(report: CampaignReport): RankedItem[] {
  return report.items
    .map((item) => ({
      ...item,
      askedContents: item.summary.answered_contents + item.summary.abstentions,
    }))
    .sort((a, b) => {
      const left = a.summary.agreement;
      const right = b.summary.agreement;
      if (left.pair_count === 0 || right.pair_count === 0) {
        return (left.pair_count === 0 ? 1 : 0) - (right.pair_count === 0 ? 1 : 0) ||
          a.order - b.order;
      }
      return (
        (right.mean_abs_diff ?? 0) - (left.mean_abs_diff ?? 0) ||
        (left.exact_pct ?? 0) - (right.exact_pct ?? 0) ||
        a.order - b.order
      );
    });
}

export interface Dimension {
  dimension: string;
  items: CampaignReportItem[];
}

/** The items grouped as the instrument groups them, both kept in the instrument's order.
 *
 * ADR-0052 §1 kept `dimension` for exactly this: a place where qualities are **read**
 * together. Never summed together — there is no dimension-level number anywhere below.
 */
export function byDimension(report: CampaignReport): Dimension[] {
  const groups = new Map<string, CampaignReportItem[]>();
  for (const item of [...report.items].sort((a, b) => a.order - b.order)) {
    const existing = groups.get(item.dimension);
    if (existing) existing.push(item);
    else groups.set(item.dimension, [item]);
  }
  return [...groups].map(([dimension, items]) => ({ dimension, items }));
}

/** Courses the panel read most differently, first.
 *
 * A course nobody has finished sorts last, for the reason an unpaired item does: it is a
 * fact about progress, and the quorum line above already says it.
 */
export function rankContents(report: CampaignReport): CampaignReportContent[] {
  return [...report.contents].sort(
    (a, b) =>
      (b.disagreement.max_abs_diff ?? -1) - (a.disagreement.max_abs_diff ?? -1) ||
      (b.disagreement.mean_abs_diff ?? -1) - (a.disagreement.mean_abs_diff ?? -1) ||
      b.submitted_count - a.submitted_count ||
      a.external_id.localeCompare(b.external_id),
  );
}

export interface Silences {
  /** Item-and-course pairs nobody was asked: the course declares nothing they are about. */
  withheld: number;
  /** Item-and-course pairs somebody was asked and could not judge. */
  abstained: number;
  /** Courses that have not reached their quorum yet. */
  awaiting: number;
  /** Items resting on a declaration, and how widely the scope actually makes it. */
  declarationBound: { qualityId: string; prompt: string; asked: number; of: number }[];
}

/** The three ways a cell can be empty, counted apart (ADR-0060 §4).
 *
 * They are one colour on the screen and three different acts: fix the generator, rewrite the
 * item, or wait.
 */
export function silences(report: CampaignReport): Silences {
  return {
    withheld: report.items.reduce((sum, item) => sum + item.summary.withheld_contents, 0),
    abstained: report.items.reduce((sum, item) => sum + item.summary.abstentions, 0),
    awaiting: report.contents.filter((content) => !content.completed).length,
    declarationBound: report.items
      .filter((item) => item.required_data.length > 0)
      .map((item) => ({
        qualityId: item.quality_id,
        prompt: item.prompt,
        asked: report.quorum.contents_in_scope - item.summary.withheld_contents,
        of: report.quorum.contents_in_scope,
      })),
  };
}

/** Every answer of the campaign as rows, for the CSV — one line per (course, assessor, item).
 *
 * Superseded corrections are included and flagged rather than dropped: what the report counts
 * is one question and what somebody actually answered is another, and a raw export that
 * silently omits rows is worse than no export.
 */
export function answerRows(report: CampaignReport): (string | number)[][] {
  const rows: (string | number)[][] = [];
  for (const content of report.contents) {
    for (const evaluation of content.evaluations) {
      for (const score of evaluation.scores) {
        rows.push([
          report.name,
          content.external_id,
          content.title ?? "",
          evaluation.assessor_name ?? evaluation.assessor_id,
          evaluation.submitted_at ?? "",
          score.quality_id,
          score.score ?? "",
          // The three empties, spelled out rather than left as a blank cell.
          score.derived ? "not asked" : score.score === null ? "abstained" : "answered",
          (score.comment ?? "").replace(/\s+/g, " "),
        ]);
      }
    }
  }
  return rows;
}

export const ANSWER_COLUMNS = [
  "campaign",
  "course_external_id",
  "course_title",
  "assessor",
  "submitted_at",
  "item",
  "score",
  "state",
  "comment",
];
