"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { useAssessors, useAssignContent, useContents } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { CampaignResponse } from "@/lib/api/types";

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
  const evaluators = useMemo(
    () => (assessors ?? []).filter((a) => a.role === "evaluator"),
    [assessors],
  );

  const [contentId, setContentId] = useState("");
  const [assessorId, setAssessorId] = useState("");

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
              {c.external_id} · v{c.version}
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
          {evaluators.map((a) => (
            <option key={a.assessor_id} value={a.assessor_id}>
              {a.display_name ?? a.email ?? a.assessor_id.slice(0, 8)}
            </option>
          ))}
        </Select>
        {evaluators.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No evaluators yet — invite them in Clerk; they appear here after their first sign-in.
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
