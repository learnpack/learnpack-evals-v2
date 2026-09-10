"use client";

import { Fragment, use, useMemo, useState } from "react";
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
import { CampaignAssignments } from "@/components/admin/campaign-assignments";
import { RenameCampaignForm } from "@/components/admin/rename-campaign-form";
import {
  useCampaignAssignments,
  useCampaignProgress,
  useCampaigns,
  useCloseCampaign,
  useContents,
  useDatasets,
  useGeneratorVersions,
  useReferenceInstruments,
} from "@/lib/api/hooks";
import { courseLabel } from "@/lib/courses";
import { campaignLoad, staffingOf } from "@/lib/assignments";
import { generatorName, groupByVersion } from "@/lib/versions";
import { ApiError } from "@/lib/api/client";
import type { ContentProgress } from "@/lib/api/types";

/** A run of the progress table under one heading. A null title is the table before it can
 *  be grouped: one run, no heading, rather than a heading that guesses. */
type ProgressSection = { key: string; title: string | null; rows: ContentProgress[] };

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
  const generatorVersions = useGeneratorVersions();
  const instruments = useReferenceInstruments();
  const datasets = useDatasets();
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

  /**
   * The campaign's courses read by the generator version that made them, with the grouping the
   * course list and the dataset picker already use (`lib/versions.ts`) — a second definition
   * of "a version's courses" would come to disagree with the first.
   *
   * The version is the course's current attribution, not a copy taken when the campaign
   * opened: a course attributed later moves group, as it does everywhere else in the console.
   *
   * Flat until both lists arrive. Grouped early, every course would sit under a heading that
   * says "unknown" where the truth is "not known yet".
   */
  const sections = useMemo((): ProgressSection[] => {
    const rows = progress.data?.contents ?? [];
    if (contents.data === undefined || generatorVersions.data === undefined) {
      return [{ key: "all", title: null, rows }];
    }
    const progressById = new Map(rows.map((row) => [row.content_id, row]));
    const courses = contents.data.filter((course) => progressById.has(course.content_id));
    const grouped = groupByVersion(courses, generatorVersions.data).map((group) => ({
      key: group.key,
      title: generatorName(group.key, group.version),
      rows: [...group.courses]
        .sort((a, b) => courseLabel(a).localeCompare(courseLabel(b)))
        .map((course) => progressById.get(course.content_id)!),
    }));
    // Not expected — content is never retired (ADR-0033) — but a course the list cannot
    // resolve is still one the campaign judges, and it must not drop out of the table.
    const listed = new Set(courses.map((course) => course.content_id));
    const unresolved = rows.filter((row) => !listed.has(row.content_id));
    return unresolved.length
      ? [...grouped, { key: "unresolved", title: "Not in the course list", rows: unresolved }]
      : grouped;
  }, [progress.data, contents.data, generatorVersions.data]);

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
  const understaffedIn = (rows: ContentProgress[]) =>
    rows.filter((c) => staffingOf(c, load.perContent.get(c.content_id) ?? 0) === "understaffed")
      .length;
  const understaffed = seatsKnown ? understaffedIn(p.contents) : 0;

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
              {sections.map((section) => (
                <Fragment key={section.key}>
                  {section.title !== null ? (
                    <SectionHeading
                      title={section.title}
                      rows={section.rows}
                      understaffed={seatsKnown ? understaffedIn(section.rows) : null}
                      columns={canAssign ? 5 : 4}
                    />
                  ) : null}
                  {section.rows.map((c) => {
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
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* No card around it: each evaluator is a card already, and one nested in another reads
          as a mistake. */}
      <section className="mt-8">
        <h2 className="mb-3 text-lg font-semibold tracking-tight">Assignments</h2>
        <CampaignAssignments campaignId={campaignId} />
      </section>

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

/**
 * One generator version's heading, with where its courses stand.
 *
 * The subtotals are why the table is grouped at all: which version is behind, and which one
 * is short of assignees, read without counting rows. `understaffed` is null while the seats
 * are not known, and then the heading says nothing about them — as the rows do.
 */
function SectionHeading({
  title,
  rows,
  understaffed,
  columns,
}: {
  title: string;
  rows: ContentProgress[];
  understaffed: number | null;
  columns: number;
}) {
  const complete = rows.filter((row) => row.completed).length;
  return (
    <TableRow className="bg-muted/40 hover:bg-muted/40">
      <TableCell colSpan={columns} className="py-2 text-xs tabular-nums text-muted-foreground">
        <span className="font-medium text-foreground">{title}</span>
        {" · "}
        {rows.length} {rows.length === 1 ? "course" : "courses"}
        {" · "}
        {complete} complete
        {understaffed ? (
          <span className="text-amber-700 dark:text-amber-400">
            {" · "}
            {understaffed} {understaffed === 1 ? "needs" : "need"} assignees
          </span>
        ) : null}
      </TableCell>
    </TableRow>
  );
}
