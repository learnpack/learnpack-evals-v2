/** What a campaign has already asked of whom, counted from the assignments it serves.
 *
 * Derived in the console rather than added to `CampaignProgress`: every screen that asks
 * this question already fetches the assignment list, so a second copy on the wire would be
 * a second thing to keep true. The tradeoff is a client-side count, which holds while a
 * campaign is a panel of experts over tens of courses — the size the first one was designed
 * for. It stops holding at thousands of assignments, and then the count belongs in the
 * backend's own read.
 *
 * Pure functions rather than a hook, for the reason `courses.ts` gives: the callers are not
 * the same caller — a table cell, a sort key, a filter predicate.
 */

import type { AssignmentResponse, ContentProgress, Uuid } from "@/lib/api/types";

/**
 * Whether an assignment occupies one of a course's seats.
 *
 * A cancelled one does not, and that is the whole rule: it is neither work somebody owes nor
 * coverage the course has. It stays visible wherever the assignment itself is listed, because
 * it is a fact about what happened — but it counts towards nothing.
 */
export function holdsASeat(assignment: AssignmentResponse): boolean {
  return assignment.status !== "cancelled";
}

/** How many seats are taken, per course and per evaluator. */
export interface CampaignLoad {
  perContent: Map<Uuid, number>;
  perAssessor: Map<Uuid, number>;
}

export function campaignLoad(assignments: AssignmentResponse[] | undefined): CampaignLoad {
  const perContent = new Map<Uuid, number>();
  const perAssessor = new Map<Uuid, number>();
  for (const assignment of assignments ?? []) {
    if (!holdsASeat(assignment)) continue;
    perContent.set(assignment.content_id, (perContent.get(assignment.content_id) ?? 0) + 1);
    perAssessor.set(assignment.assessor_id, (perAssessor.get(assignment.assessor_id) ?? 0) + 1);
  }
  return { perContent, perAssessor };
}

/**
 * Where a course stands, in the terms of what unblocks it.
 *
 * The distinction the console was missing: a course nobody is assigned to and a course whose
 * evaluators have not answered yet are both "in progress", and they are not the same
 * situation. `understaffed` is the one an admin resolves by acting; the other one is resolved
 * by the panel, or by waiting for it.
 */
export type Staffing = "understaffed" | "in-progress" | "complete";

export function staffingOf(content: ContentProgress, assigned: number): Staffing {
  if (content.completed) return "complete";
  return assigned < content.required ? "understaffed" : "in-progress";
}
