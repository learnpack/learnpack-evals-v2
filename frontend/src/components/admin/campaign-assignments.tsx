"use client";

import { useMemo } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useAssessors,
  useCampaignAssignments,
  useCancelAssignment,
  useContents,
} from "@/lib/api/hooks";
import { holdsASeat } from "@/lib/assignments";
import { courseLabel } from "@/lib/courses";
import { ApiError } from "@/lib/api/client";
import type { AssignmentResponse, Uuid } from "@/lib/api/types";

/**
 * What a campaign asked of each evaluator, read as people rather than as rows.
 *
 * The unit is the person because that is the question the list is opened with — who is
 * overloaded, who has not started, who is free. Flat, one row per (evaluator, course), a
 * campaign of forty courses and two raters is eighty rows and answers none of it. Reporting
 * reaches the same conclusion for its cross-campaign read (`reporting/.../reports.py`).
 *
 * Collapsed by default, so the closed row has to carry the answer on its own: a ratio of what
 * came back over what was asked, and a badge for the two states worth acting on.
 *
 * Cancelled assignments are listed but not counted (`lib/assignments.ts`): they are neither
 * work owed nor coverage given, and hiding them would erase the fact that somebody was asked.
 *
 * It fetches what it needs itself rather than taking it as props: the page around it holds the
 * same three queries, and React Query serves both readers from one cache entry.
 */
export function CampaignAssignments({ campaignId }: { campaignId: Uuid }) {
  const assignments = useCampaignAssignments(campaignId);
  const assessors = useAssessors();
  const contents = useContents();
  const cancelAssignment = useCancelAssignment(campaignId);

  const contentName = useMemo(() => {
    const map = new Map((contents.data ?? []).map((c) => [c.content_id, c]));
    return (id: string) => courseLabel(map.get(id), id);
  }, [contents.data]);

  /** One group per evaluator who carries something, busiest first — the section answers
   *  "who is this campaign waiting on", so the answer goes at the top. Alphabetical would
   *  bury it under whoever happens to be called Ana. */
  const groups = useMemo(() => {
    const names = new Map(
      (assessors.data ?? []).map((a) => [a.assessor_id, a.display_name ?? a.email ?? null]),
    );
    const byAssessor = new Map<Uuid, AssignmentResponse[]>();
    for (const assignment of assignments.data ?? []) {
      const held = byAssessor.get(assignment.assessor_id);
      if (held) held.push(assignment);
      else byAssessor.set(assignment.assessor_id, [assignment]);
    }
    return [...byAssessor.entries()]
      .map(([assessorId, held]) => {
        const seats = held.filter(holdsASeat);
        const submitted = seats.filter((a) => a.status === "submitted").length;
        const opened = seats.filter((a) => a.status === "opened").length;
        return {
          assessorId,
          name: names.get(assessorId) ?? assessorId.slice(0, 8),
          held,
          assigned: seats.length,
          submitted,
          pending: seats.length - submitted,
          untouched: opened === 0 && submitted === 0,
        };
      })
      .sort((a, b) => b.pending - a.pending || a.name.localeCompare(b.name));
  }, [assignments.data, assessors.data]);

  /** Nobody with nothing assigned can appear above, and that absence is the point: an
   *  evaluator this campaign never asked anything of is the first person to ask. */
  const idle = useMemo(() => {
    const carrying = new Set(groups.filter((g) => g.assigned > 0).map((g) => g.assessorId));
    return (assessors.data ?? []).filter(
      (a) => a.role === "evaluator" && a.status === "active" && !carrying.has(a.assessor_id),
    ).length;
  }, [groups, assessors.data]);

  function handleCancel(assignmentId: Uuid) {
    cancelAssignment.mutate(assignmentId, {
      onSuccess: () => toast.success("Assignment cancelled."),
      onError: (err) => {
        const e = err as ApiError;
        if (e.status === 409) {
          toast.error("A submitted assignment can't be cancelled.");
        } else {
          toast.error("Could not cancel.", { description: e.message });
        }
      },
    });
  }

  if (assignments.isLoading) return <LoadingState />;
  if (!assignments.data || assignments.data.length === 0) {
    return <p className="text-sm text-muted-foreground">No assignments yet.</p>;
  }

  return (
    <div className="space-y-2">
      {groups.map((group) => (
        <CollapsibleSection
          key={group.assessorId}
          defaultOpen={false}
          title={group.name}
          meta={
            <span className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">
                {group.submitted}/{group.assigned} submitted
              </Badge>
              {group.assigned === 0 ? (
                <Badge variant="outline">all cancelled</Badge>
              ) : group.pending === 0 ? (
                <Badge variant="success">done</Badge>
              ) : group.untouched ? (
                <Badge variant="warning">nothing opened yet</Badge>
              ) : null}
            </span>
          }
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Course</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {group.held.map((a) => {
                const cancellable = a.status === "assigned" || a.status === "opened";
                return (
                  <TableRow key={a.assignment_id} className={holdsASeat(a) ? undefined : "opacity-60"}>
                    <TableCell className="font-medium">{contentName(a.content_id)}</TableCell>
                    <TableCell>
                      <Badge variant={a.status === "submitted" ? "success" : "secondary"}>
                        {a.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {cancellable ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCancel(a.assignment_id)}
                          disabled={cancelAssignment.isPending}
                        >
                          Cancel
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CollapsibleSection>
      ))}
      {idle > 0 ? (
        <p className="pt-1 text-sm text-muted-foreground">
          {idle} active {idle === 1 ? "evaluator has" : "evaluators have"} nothing assigned in
          this campaign.
        </p>
      ) : null}
    </div>
  );
}
