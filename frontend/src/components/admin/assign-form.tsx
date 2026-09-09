"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { EvaluatorPicker } from "@/components/admin/evaluator-picker";
import { toggleIn } from "@/components/admin/course-picker";
import {
  useAssessors,
  useAssignContents,
  useCampaignAssignments,
  useCampaignProgress,
  useContents,
} from "@/lib/api/hooks";
import { isAssignableEvaluator } from "@/lib/assessors";
import { campaignLoad, holdsASeat } from "@/lib/assignments";
import { courseLabel } from "@/lib/courses";
import { ApiError } from "@/lib/api/client";
import type { CampaignResponse } from "@/lib/api/types";

/**
 * How many assignments in this campaign is enough for one expert, as the form assumes it
 * until somebody says otherwise.
 *
 * Four is the ceiling the first panel was sized against, and it lives nowhere else: not in the
 * domain, not in the campaign, not in the store. So it is a default of this control and
 * nothing more — typed over on the spot, and never enforced.
 */
const ASSIGNMENTS_PER_EVALUATOR = "4";

export function AssignForm({
  campaign,
  contentId: preselected,
  onDone,
}: {
  campaign: CampaignResponse;
  /** The course the form opens on, when it was opened from that course's row. Preselected
   *  and not locked: a misclick should cost a second click, not the whole dialog. */
  contentId?: string;
  onDone: () => void;
}) {
  const { data: contents } = useContents();
  const { data: assessors } = useAssessors();
  const { data: assignments } = useCampaignAssignments(campaign.campaign_id);
  const { data: progress } = useCampaignProgress(campaign.campaign_id);
  const assign = useAssignContents(campaign.campaign_id);

  const courses = useMemo(
    () => (contents ?? []).filter((c) => campaign.content_ids.includes(c.content_id)),
    [contents, campaign.content_ids],
  );
  // Deactivated people are dropped rather than disabled: unlike a course with no consumable
  // URL, there is nothing here for a reason to explain — they left, and offering the row
  // would only invite an act that the server refuses anyway (ADR-0051). Automated assessors
  // are dropped for a stronger reason — there is nobody there to open the course.
  const evaluators = useMemo(() => (assessors ?? []).filter(isAssignableEvaluator), [assessors]);

  const load = useMemo(() => campaignLoad(assignments), [assignments]);
  const loadOf = useMemo(
    () => (assessorId: string) => load.perAssessor.get(assessorId) ?? 0,
    [load],
  );

  const [contentId, setContentId] = useState(preselected ?? "");
  const [assessorIds, setAssessorIds] = useState<string[]>([]);
  const [onlyShort, setOnlyShort] = useState(true);
  const [ceiling, setCeiling] = useState(ASSIGNMENTS_PER_EVALUATOR);

  /** Who is on the chosen course already — the 409 the server would answer with, said before
   *  it is provoked. Empty until a course is chosen, which is also when it means nothing. */
  const alreadyOnCourse = useMemo(() => {
    const on = new Set<string>();
    if (!contentId) return on;
    for (const a of assignments ?? []) {
      if (a.content_id === contentId && holdsASeat(a)) on.add(a.assessor_id);
    }
    return on;
  }, [assignments, contentId]);

  /** Which courses of this campaign still have fewer evaluators than its quorum. */
  const short = useMemo(() => {
    const ids = new Set<string>();
    for (const c of progress?.contents ?? []) {
      if ((load.perContent.get(c.content_id) ?? 0) < c.required) ids.add(c.content_id);
    }
    return ids;
  }, [progress, load]);

  // Hidden, not disabled — and that is not the absence ADR-0028 argues against: this one the
  // reader switched on, can switch off, and is told the size of. What that rule forbids is an
  // option gone for a reason nobody can see.
  // Until the progress arrives, no course is known to be short, and filtering on that would
  // empty the list rather than shorten it.
  const filtering = onlyShort && progress !== undefined;
  const shown = useMemo(
    () =>
      filtering
        ? courses.filter((c) => short.has(c.content_id) || c.content_id === contentId)
        : courses,
    [courses, filtering, short, contentId],
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!contentId || assessorIds.length === 0) {
      toast.error("Pick a course and at least one evaluator.");
      return;
    }
    assign.mutate(
      { content_id: contentId, assessor_ids: assessorIds },
      {
        onSuccess: (outcome) => {
          const asked = assessorIds.length;
          if (outcome.assigned === asked) {
            toast.success(asked === 1 ? "Assigned." : `Assigned to ${asked} evaluators.`);
            onDone();
            return;
          }
          // Partial, and said as such: what went through stays through, and the form stays
          // open on the rest rather than closing over a half-done act.
          const notes = [
            outcome.duplicates > 0 ? `${outcome.duplicates} already assigned` : null,
            ...outcome.errors,
          ].filter(Boolean);
          toast.warning(`Assigned to ${outcome.assigned} of ${asked}.`, {
            description: notes.join(" · "),
          });
          if (outcome.assigned > 0) onDone();
        },
        onError: (err) => {
          toast.error("Could not assign.", { description: (err as ApiError).message });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label>Course</Label>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={onlyShort}
            onChange={() => setOnlyShort((v) => !v)}
            className="h-4 w-4"
          />
          Only courses below the quorum of {campaign.required_evaluations_per_content}
        </label>
        {/* Disabled with its reason, not filtered out (ADR-0028): an absent option reads as
            a bug, a disabled one reads as a fact. This is the act that would put a human in
            front of nothing, so this is where the refusal belongs — advisory for now, the
            server does not enforce it (STATUS). */}
        <Select value={contentId} onChange={(e) => setContentId(e.target.value)}>
          <option value="">Select a course…</option>
          {shown.map((c) => (
            <option key={c.content_id} value={c.content_id} disabled={!c.consumable_url}>
              {courseLabel(c)} · v{c.version}
              {c.consumable_url ? "" : " — not deployed"}
            </option>
          ))}
        </Select>
        {filtering && shown.length < courses.length ? (
          <p className="text-xs text-muted-foreground">
            {courses.length - shown.length} of {courses.length} courses hidden — they already
            have the quorum assigned.
          </p>
        ) : null}
        {shown.some((c) => !c.consumable_url) ? (
          <p className="text-xs text-muted-foreground">
            Courses marked <span className="font-medium">not deployed</span> declare no
            consumable URL, so there is nothing for an evaluator to open. They can still be
            evaluated automatically.
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <Label>Evaluators</Label>
        <EvaluatorPicker
          evaluators={evaluators}
          loadOf={loadOf}
          alreadyAssigned={alreadyOnCourse}
          selected={assessorIds}
          onToggle={(id) => setAssessorIds((ids) => toggleIn(ids, id))}
          ceiling={ceiling}
          onCeilingChange={setCeiling}
        />
        {evaluators.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No evaluators yet — invite them from{" "}
            <Link href="/admin/assessors" className="underline">
              Assessors
            </Link>
            ; they appear here after their first sign-in.
          </p>
        ) : null}
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="outline" onClick={onDone} disabled={assign.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={assign.isPending}>
          {assign.isPending ? <Spinner /> : null}
          Assign
          {assessorIds.length > 1 ? ` to ${assessorIds.length}` : ""}
        </Button>
      </div>
    </form>
  );
}
