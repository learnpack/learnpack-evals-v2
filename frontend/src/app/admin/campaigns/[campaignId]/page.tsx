"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, BarChart3, Pencil, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AssignForm } from "@/components/admin/assign-form";
import { RenameCampaignForm } from "@/components/admin/rename-campaign-form";
import {
  useAssessors,
  useCampaignAssignments,
  useCampaignProgress,
  useCampaigns,
  useCancelAssignment,
  useCloseCampaign,
  useContents,
  useDatasets,
  useReferenceInstruments,
} from "@/lib/api/hooks";
import { courseLabel } from "@/lib/courses";
import { campaignLoad, staffingOf } from "@/lib/assignments";
import { ApiError } from "@/lib/api/client";

export default function CampaignDetailPage({
  params,
}: {
  params: Promise<{ campaignId: string }>;
}) {
  const { campaignId } = use(params);
  const campaigns = useCampaigns();
  const progress = useCampaignProgress(campaignId);
  const assignments = useCampaignAssignments(campaignId);
  const contents = useContents();
  const assessors = useAssessors();
  const instruments = useReferenceInstruments();
  const datasets = useDatasets();
  const cancelAssignment = useCancelAssignment(campaignId);
  const closeCampaign = useCloseCampaign();
  /** Null while closed; the course it opens on when it was opened from that course's row,
   *  and `{}` when it was opened from the header, which commits to no course. */
  const [assigning, setAssigning] = useState<{ contentId?: string } | null>(null);
  const [renaming, setRenaming] = useState(false);

  const campaign = campaigns.data?.find((c) => c.campaign_id === campaignId);

  const contentById = useMemo(
    () => new Map((contents.data ?? []).map((c) => [c.content_id, c])),
    [contents.data],
  );

  const contentName = useMemo(
    () => (id: string) => courseLabel(contentById.get(id), id),
    [contentById],
  );

  /** How many seats each course has taken, counted from the assignment list this page already
   *  fetches (`lib/assignments.ts`). It is a different question from `submitted_count`, which
   *  keeps coming from the backend: one says whether anybody was asked, the other whether they
   *  answered. */
  const load = useMemo(() => campaignLoad(assignments.data), [assignments.data]);

  // The raw id while the list loads, and for a version the list no longer offers — a draft,
  // or one dropped from the store. A campaign keeps pinning it either way (ADR-0056).
  const instrumentName = useMemo(() => {
    const match = (instruments.data ?? []).find(
      (i) => i.rubric_version_id === progress.data?.instrument_version_id,
    );
    return match ? `${match.name} · ${match.version}` : progress.data?.instrument_version_id;
  }, [instruments.data, progress.data]);

  /** Where this campaign's scope came from (ADR-0058 §5). Null on campaigns opened before
   *  the decision — they were typed into a form, and the line says so rather than guessing. */
  const scopeOrigin = useMemo(() => {
    if (!campaign?.dataset_version_id) return null;
    for (const dataset of datasets.data ?? []) {
      const version = dataset.versions.find(
        (v) => v.version_id === campaign.dataset_version_id,
      );
      if (version) return { dataset, version };
    }
    return null;
  }, [campaign, datasets.data]);

  const assessorName = useMemo(() => {
    const map = new Map(
      (assessors.data ?? []).map((a) => [a.assessor_id, a.display_name ?? a.email ?? a.assessor_id]),
    );
    return (id: string) => map.get(id) ?? id.slice(0, 8);
  }, [assessors.data]);

  function handleCancel(assignmentId: string) {
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

  function handleClose() {
    closeCampaign.mutate(campaignId, {
      onSuccess: () => toast.success("Campaign closed."),
      onError: (err) => toast.error("Could not close.", { description: (err as ApiError).message }),
    });
  }

  if (progress.isLoading || campaigns.isLoading) return <LoadingState />;
  if (progress.error) return <ErrorState message={(progress.error as Error).message} />;
  if (!progress.data) return <ErrorState message="Campaign not found." />;

  const p = progress.data;
  const canAssign = p.status === "open";

  /** Until the assignments arrive, every course would count zero seats — and `0/2` beside a
   *  call to action is not an unknown, it is a false claim that nobody was asked. So the
   *  staffing reading waits, and the table says as much. */
  const seatsKnown = assignments.data !== undefined;
  const understaffed = seatsKnown
    ? p.contents.filter(
        (c) => staffingOf(c, load.perContent.get(c.content_id) ?? 0) === "understaffed",
      ).length
    : 0;

  return (
    <div className="max-w-5xl">
      <Link
        href="/admin/campaigns"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> All campaigns
      </Link>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-3 text-2xl font-semibold tracking-tight">
            {campaign?.name}
            <Badge variant={p.status === "open" ? "success" : "secondary"}>{p.status}</Badge>
          </h1>
          {campaign?.description ? (
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{campaign.description}</p>
          ) : null}
          <p className="mt-1 text-sm text-muted-foreground">
            {instrumentName} · quorum {p.required_evaluations_per_content} · coverage{" "}
            {Math.round(p.coverage * 100)}%
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {scopeOrigin ? (
              <>
                {p.contents.length} courses from{" "}
                <Link
                  href={`/admin/datasets/${scopeOrigin.dataset.dataset_id}`}
                  className="underline"
                >
                  {scopeOrigin.dataset.name}
                </Link>{" "}
                v{scopeOrigin.version.ordinal}
              </>
            ) : (
              `${p.contents.length} courses, chosen before sets were named`
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/admin/campaigns/${campaignId}/report`}
            className={buttonVariants({ variant: "outline" })}
          >
            <BarChart3 className="h-4 w-4" /> View report
          </Link>
          {/* In any status: a label binds nothing, so closing does not protect it (ADR-0055). */}
          {campaign ? (
            <Button variant="outline" onClick={() => setRenaming(true)}>
              <Pencil className="h-4 w-4" /> Rename
            </Button>
          ) : null}
          {canAssign ? (
            <Button onClick={() => setAssigning({})}>
              <Plus className="h-4 w-4" /> Assign
            </Button>
          ) : null}
          {p.status === "open" ? (
            <Button variant="outline" onClick={handleClose} disabled={closeCampaign.isPending}>
              Close campaign
            </Button>
          ) : null}
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Per-course progress</CardTitle>
          {/* The one number worth reading before any row: how much of the campaign is waiting
              on an act of this console rather than on the panel. */}
          {understaffed > 0 ? (
            <p className="text-sm text-muted-foreground">
              {understaffed} of {p.contents.length} courses below quorum in assignments.
            </p>
          ) : null}
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Course</TableHead>
                <TableHead>Assigned</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Status</TableHead>
                {canAssign ? <TableHead className="text-right">Actions</TableHead> : null}
              </TableRow>
            </TableHeader>
            <TableBody>
              {p.contents.map((c) => {
                const assigned = load.perContent.get(c.content_id) ?? 0;
                const staffing = seatsKnown ? staffingOf(c, assigned) : null;
                const course = contentById.get(c.content_id);
                return (
                  <TableRow key={c.content_id}>
                    <TableCell className="font-medium">{contentName(c.content_id)}</TableCell>
                    <TableCell>{seatsKnown ? `${assigned}/${c.required}` : "—"}</TableCell>
                    <TableCell>
                      {c.submitted_count}/{c.required}
                    </TableCell>
                    <TableCell>
                      {/* Three states, because two hid the difference that matters: a course
                          nobody was assigned to and a course whose panel has not answered yet
                          are not the same situation, and only the first one is ours to fix. */}
                      {staffing === "understaffed" ? (
                        <Badge variant="warning">needs assignees</Badge>
                      ) : c.completed ? (
                        <Badge variant="success">complete</Badge>
                      ) : (
                        <Badge variant="outline">in progress</Badge>
                      )}
                    </TableCell>
                    {canAssign ? (
                      <TableCell className="text-right">
                        {/* Offered on every row, not only the short ones: assigning past the
                            quorum against expected dropout is deliberate. The badge carries
                            the signal; the button carries the act. */}
                        {course && !course.consumable_url ? (
                          <span className="text-xs text-muted-foreground">not deployed</span>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setAssigning({ contentId: c.content_id })}
                          >
                            Assign
                          </Button>
                        )}
                      </TableCell>
                    ) : null}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Assignments</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {assignments.isLoading ? (
            <div className="p-6">
              <LoadingState />
            </div>
          ) : !assignments.data || assignments.data.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">No assignments yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Evaluator</TableHead>
                  <TableHead>Course</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {assignments.data.map((a) => {
                  const cancellable = a.status === "assigned" || a.status === "opened";
                  return (
                    <TableRow key={a.assignment_id}>
                      <TableCell className="font-medium">{assessorName(a.assessor_id)}</TableCell>
                      <TableCell>{contentName(a.content_id)}</TableCell>
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
          )}
        </CardContent>
      </Card>

      {campaign ? (
        <>
          <Dialog
            open={assigning !== null}
            onClose={() => setAssigning(null)}
            title="Assign a course"
            description="Give an evaluator a course from this campaign."
          >
            <AssignForm
              campaign={campaign}
              contentId={assigning?.contentId}
              onDone={() => setAssigning(null)}
            />
          </Dialog>

          <Dialog
            open={renaming}
            onClose={() => setRenaming(false)}
            title="Rename this campaign"
            description="Only the label changes. Nothing about what the campaign measures moves."
          >
            <RenameCampaignForm campaign={campaign} onDone={() => setRenaming(false)} />
          </Dialog>
        </>
      ) : null}
    </div>
  );
}
