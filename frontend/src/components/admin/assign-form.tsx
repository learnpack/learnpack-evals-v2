"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { useAssessors, useAssignContent, useContents } from "@/lib/api/hooks";
import { courseLabel } from "@/lib/courses";
import { ApiError } from "@/lib/api/client";
import type { CampaignResponse } from "@/lib/api/types";

/**
 * How much of an expertise profile fits beside a name in a native `<option>`.
 *
 * The control has a fixed width and its options carry no styling of their own, so a long
 * profile either pushes the name out of view or gets cut by the browser mid-word with no
 * sign that anything is missing. Cutting it here at least ends in an ellipsis, and the full
 * text is shown under the control once somebody is selected.
 */
const EXPERTISE_IN_OPTION = 48;

function shorten(text: string): string {
  const clean = text.trim();
  if (clean.length <= EXPERTISE_IN_OPTION) return clean;
  // Break on a space when there is one nearby, so the cut does not land mid-word.
  const cut = clean.slice(0, EXPERTISE_IN_OPTION);
  const lastSpace = cut.lastIndexOf(" ");
  return `${(lastSpace > EXPERTISE_IN_OPTION - 12 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

export function AssignForm({
  campaign,
  onDone,
}: {
  campaign: CampaignResponse;
  onDone: () => void;
}) {
  const { data: contents } = useContents();
  const { data: assessors } = useAssessors();
  const assign = useAssignContent(campaign.campaign_id);

  const courses = useMemo(
    () => (contents ?? []).filter((c) => campaign.content_ids.includes(c.content_id)),
    [contents, campaign.content_ids],
  );
  // Deactivated people are dropped rather than disabled: unlike a course with no consumable
  // URL, there is nothing here for a reason to explain — they left, and offering the row
  // would only invite an act that the server refuses anyway (ADR-0051).
  const evaluators = useMemo(
    () => (assessors ?? []).filter((a) => a.role === "evaluator" && a.status === "active"),
    [assessors],
  );

  const [contentId, setContentId] = useState("");
  const [assessorId, setAssessorId] = useState("");
  const selected = useMemo(
    () => evaluators.find((a) => a.assessor_id === assessorId),
    [evaluators, assessorId],
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!contentId || !assessorId) {
      toast.error("Pick a course and an evaluator.");
      return;
    }
    assign.mutate(
      { content_id: contentId, assessor_id: assessorId },
      {
        onSuccess: () => {
          toast.success("Assigned.");
          onDone();
        },
        onError: (err) => {
          const e = err as ApiError;
          if (e.status === 409) {
            toast.error("That evaluator is already assigned to this course.");
          } else {
            toast.error("Could not assign.", { description: e.message });
          }
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label>Course</Label>
        {/* Disabled with its reason, not filtered out (ADR-0028): an absent option reads as
            a bug, a disabled one reads as a fact. This is the act that would put a human in
            front of nothing, so this is where the refusal belongs — advisory for now, the
            server does not enforce it (STATUS). */}
        <Select value={contentId} onChange={(e) => setContentId(e.target.value)}>
          <option value="">Select a course…</option>
          {courses.map((c) => (
            <option key={c.content_id} value={c.content_id} disabled={!c.consumable_url}>
              {courseLabel(c)} · v{c.version}
              {c.consumable_url ? "" : " — not deployed"}
            </option>
          ))}
        </Select>
        {courses.some((c) => !c.consumable_url) ? (
          <p className="text-xs text-muted-foreground">
            Courses marked <span className="font-medium">not deployed</span> declare no
            consumable URL, so there is nothing for an evaluator to open. They can still be
            evaluated automatically.
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <Label>Evaluator</Label>
        <Select value={assessorId} onChange={(e) => setAssessorId(e.target.value)}>
          <option value="">Select an evaluator…</option>
          {/* The expertise profile rides in the label because this is the act it exists for:
              deciding who should read *this* course. A native <option> takes no markup and
              no width of its own, so it is appended and shortened; the whole profile of
              whoever ends up selected is shown under the control, where it has room. */}
          {evaluators.map((a) => (
            <option key={a.assessor_id} value={a.assessor_id}>
              {a.display_name ?? a.email ?? a.assessor_id.slice(0, 8)}
              {a.expertise ? ` — ${shorten(a.expertise)}` : ""}
            </option>
          ))}
        </Select>
        {selected?.expertise ? (
          <p className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Expertise:</span>{" "}
            {selected.expertise}
          </p>
        ) : null}
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
        </Button>
      </div>
    </form>
  );
}
