"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Pencil, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  useGoldenStatus,
  useDatasets,
  useReferenceInstruments,
} from "@/lib/api/hooks";
import { courseLabel } from "@/lib/courses";
import { ApiError } from "@/lib/api/client";

export default function CampaignDetailPage({
  params,
}: {
  params: Promise<{ campaignId: string }>;
}) {
  const { campaignId } = use(params);
  const campaigns = useCampaigns();
  const progress = useCampaignProgress(campaignId);
  const golden = useGoldenStatus(campaignId);
  const assignments = useCampaignAssignments(campaignId);
  const contents = useContents();
  const assessors = useAssessors();
  const instruments = useReferenceInstruments();
  const datasets = useDatasets();
  const cancelAssignment = useCancelAssignment(campaignId);
  const closeCampaign = useCloseCampaign();
  const [assigning, setAssigning] = useState(false);
  const [renaming, setRenaming] = useState(false);

  const campaign = campaigns.data?.find((c) => c.campaign_id === campaignId);

  const contentName = useMemo(() => {
    const map = new Map((contents.data ?? []).map((c) => [c.content_id, c]));
    return (id: string) => courseLabel(map.get(id), id);
  }, [contents.data]);

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
          {/* In any status: a label binds nothing, so closing does not protect it (ADR-0055). */}
          {campaign ? (
            <Button variant="outline" onClick={() => setRenaming(true)}>
              <Pencil className="h-4 w-4" /> Rename
            </Button>
          ) : null}
          {canAssign ? (
            <Button onClick={() => setAssigning(true)}>
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

      <GoldenBadge
        loading={golden.isLoading}
        data={golden.data}
      />

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Per-course progress</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Course</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Complete</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {p.contents.map((c) => (
                <TableRow key={c.content_id}>
                  <TableCell className="font-medium">{contentName(c.content_id)}</TableCell>
                  <TableCell>
                    {c.submitted_count}/{c.required}
                  </TableCell>
                  <TableCell>
                    {c.completed ? (
                      <Badge variant="success">complete</Badge>
                    ) : (
                      <Badge variant="outline">in progress</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
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
            open={assigning}
            onClose={() => setAssigning(false)}
            title="Assign a course"
            description="Give an evaluator a course from this campaign."
          >
            <AssignForm campaign={campaign} onDone={() => setAssigning(false)} />
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

function GoldenBadge({
  loading,
  data,
}: {
  loading: boolean;
  data: ReturnType<typeof useGoldenStatus>["data"];
}) {
  if (loading || !data) return null;
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div>
          <p className="text-sm font-medium">Golden reference</p>
          <p className="text-xs text-muted-foreground">
            Coverage {Math.round(data.coverage * 100)}% · threshold{" "}
            {Math.round(data.threshold * 100)}%
            {data.established_at ? ` · established ${new Date(data.established_at).toLocaleDateString()}` : ""}
          </p>
        </div>
        {data.usable ? (
          <Badge variant="success">usable</Badge>
        ) : (
          <Badge variant="outline">not yet</Badge>
        )}
      </CardContent>
    </Card>
  );
}
