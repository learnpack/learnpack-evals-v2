"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, Pencil, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorState, LoadingState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DatasetVersionForm } from "@/components/admin/dataset-version-form";
import { RenameDatasetForm } from "@/components/admin/rename-dataset-form";
import { useBriefs, useContents, useDataset, useGeneratorVersions } from "@/lib/api/hooks";
import { courseLabel, courseRef } from "@/lib/courses";
import {
  latestVersion,
  summarizeMembership,
  versionHistory,
  type MembershipDiff,
  type MembershipSummary,
} from "@/lib/datasets";
import type {
  ContentResponse,
  DatasetVersionResponse,
  GeneratorVersionResponse,
  Uuid,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** A version is identified as "<lineage> <version>" everywhere it is named. */
const generatorName = (g?: GeneratorVersionResponse) => (g ? `${g.name} ${g.version}` : undefined);

export default function DatasetPage({ params }: { params: Promise<{ datasetId: string }> }) {
  const { datasetId } = use(params);
  const { data: dataset, isLoading, error } = useDataset(datasetId);
  const { data: courses } = useContents();
  // The two facts that decide what can be done with a course: the commission it shares (the
  // pairing key) and the generator that made it. Neither is required for the rest of the
  // table — while they load, those cells read as unresolved rather than as a problem.
  const { data: briefs } = useBriefs();
  const { data: generators } = useGeneratorVersions();

  const [renaming, setRenaming] = useState(false);
  const [versioning, setVersioning] = useState(false);
  // Null means "whichever is latest", so a new version selects itself instead of leaving the
  // page pointing at the one that was newest when it loaded.
  const [selectedId, setSelectedId] = useState<Uuid | null>(null);

  const courseById = useMemo(
    () => new Map((courses ?? []).map((c) => [c.content_id, c])),
    [courses],
  );
  const briefById = useMemo(() => new Map((briefs ?? []).map((b) => [b.brief_id, b])), [briefs]);
  const generatorById = useMemo(
    () => new Map((generators ?? []).map((g) => [g.generator_version_id, g])),
    [generators],
  );

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!dataset) return <ErrorState message="Dataset not found." />;

  const latest = latestVersion(dataset);
  const history = versionHistory(dataset);
  const selected = dataset.versions.find((v) => v.version_id === selectedId) ?? latest;
  const summary = summarizeMembership(selected?.content_ids ?? [], courses);

  const courseName = (id: Uuid) => courseLabel(courseById.get(id), id);
  // Sorted by the name a person reads. The API returns the canonical (uuid) order, which is
  // what makes two memberships comparable and what makes forty rows unreadable.
  const members = [...(selected?.content_ids ?? [])].sort((a, b) =>
    courseName(a).localeCompare(courseName(b)),
  );

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <Link
          href="/admin/datasets"
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> All datasets
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-3 text-2xl font-semibold tracking-tight">
              {dataset.name}
              <Badge variant="outline">v{latest?.ordinal ?? "?"}</Badge>
            </h1>
            {dataset.description ? (
              <p className="mt-1 text-sm text-muted-foreground">{dataset.description}</p>
            ) : null}
            <p className="mt-2 text-sm text-muted-foreground">
              {latest?.content_ids.length ?? 0} courses · {dataset.versions.length}{" "}
              {dataset.versions.length === 1 ? "version" : "versions"}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button variant="outline" onClick={() => setRenaming(true)}>
              <Pencil className="h-4 w-4" /> Rename
            </Button>
            <Button onClick={() => setVersioning(true)}>
              <Plus className="h-4 w-4" /> New version
            </Button>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Version history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {history.map(({ version, diff }) => (
            <VersionRow
              key={version.version_id}
              version={version}
              diff={diff}
              isLatest={version.version_id === latest?.version_id}
              isSelected={version.version_id === selected?.version_id}
              onSelect={() => setSelectedId(version.version_id)}
              courseName={courseName}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Courses in v{selected?.ordinal ?? "?"}</CardTitle>
          {/* Suppressed entirely until the courses load: "0 not deployed" and "not known
              yet" must never look the same. */}
          {summary ? <ReadinessLine summary={summary} /> : null}
        </CardHeader>
        <CardContent className="space-y-3">
          {summary && summary.undeployed > 0 ? (
            <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
              {summary.undeployed} of these courses{" "}
              {summary.undeployed === 1 ? "declares" : "declare"} no deployed instance, so{" "}
              {summary.undeployed === 1 ? "it" : "they"} cannot be handed to a human evaluator.
              A campaign over this version will still open; the assignment is what refuses.
            </p>
          ) : null}

          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Course</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Format</TableHead>
                  <TableHead>Brief</TableHead>
                  <TableHead>Generator</TableHead>
                  <TableHead>Deployment</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {members.map((id) => (
                  <CourseRow
                    key={id}
                    contentId={id}
                    course={courseById.get(id)}
                    briefText={(briefId) => briefById.get(briefId)?.brief}
                    generatorLabel={(versionId) => generatorName(generatorById.get(versionId))}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Outside the cards, so neither can unmount one mid-flight. */}
      <Dialog
        open={renaming}
        onClose={() => setRenaming(false)}
        title="Rename this dataset"
        description="The label only. It mints no version — the set does not move."
      >
        <RenameDatasetForm dataset={dataset} onDone={() => setRenaming(false)} />
      </Dialog>

      <Dialog
        open={versioning}
        onClose={() => setVersioning(false)}
        title="Freeze a new version"
        description="Edit the membership and say what changed. The version is immutable once frozen."
      >
        <DatasetVersionForm dataset={dataset} onDone={() => setVersioning(false)} />
      </Dialog>
    </div>
  );
}

/** What this membership is made of, in one line: totals first, then only what is missing. */
function ReadinessLine({ summary }: { summary: MembershipSummary }) {
  const facts = [
    `${summary.total} ${summary.total === 1 ? "course" : "courses"}`,
    summary.undeployed ? `${summary.undeployed} not deployed` : null,
    summary.withoutBrief ? `${summary.withoutBrief} without a brief` : null,
    summary.generatorVersions
      ? `${summary.generatorVersions} generator ${summary.generatorVersions === 1 ? "version" : "versions"}`
      : null,
    summary.withoutGenerator ? `${summary.withoutGenerator} without a generator` : null,
    summary.formats.length > 1 ? summary.formats.join(" + ") : null,
  ].filter(Boolean);

  return <p className="text-sm text-muted-foreground">{facts.join(" · ")}</p>;
}

/** One member, read-only. Declaring a deployment or attributing a generator are acts of
 *  `/admin/contents`: this page reads a set, it does not administer courses. */
function CourseRow({
  contentId,
  course,
  briefText,
  generatorLabel,
}: {
  contentId: Uuid;
  course: ContentResponse | undefined;
  briefText: (briefId: Uuid) => string | undefined;
  generatorLabel: (versionId: Uuid) => string | undefined;
}) {
  if (!course) {
    // Not expected — content is never retired (ADR-0033) — so it reads as unresolved rather
    // than as a course that is missing something.
    return (
      <TableRow>
        <TableCell className="font-mono font-medium">{courseRef(contentId)}</TableCell>
        <TableCell colSpan={5} className="text-xs text-muted-foreground">
          not in the course list
        </TableCell>
      </TableRow>
    );
  }

  return (
    <TableRow>
      {/* The name, with the identity under it: this page is read to decide what is in a
          set, and typed back into a command afterwards (ADR-0059 §2). */}
      <TableCell className="font-medium">
        {course.title ? (
          <>
            {course.title}
            <span className="mt-0.5 block font-mono text-xs font-normal text-muted-foreground">
              {course.external_id}
            </span>
          </>
        ) : (
          course.external_id
        )}
      </TableCell>
      <TableCell>{course.version}</TableCell>
      <TableCell className="text-muted-foreground">{course.package_format}</TableCell>
      <TableCell className="max-w-xs">
        {course.brief_id ? (
          <span className="line-clamp-2 text-xs" title={course.brief_id}>
            {briefText(course.brief_id) ?? course.brief_id}
          </span>
        ) : (
          <span
            className="text-xs text-muted-foreground"
            title="No brief recorded: this course cannot enter a brief-paired dataset."
          >
            absent
          </span>
        )}
      </TableCell>
      <TableCell className="text-xs">
        {course.generator_version_id ? (
          <span title={course.generator_version_id}>
            {generatorLabel(course.generator_version_id) ?? course.generator_version_id}
            {course.generator_attributed_at ? (
              <span className="ml-1 text-muted-foreground">(attributed later)</span>
            ) : null}
          </span>
        ) : (
          <span
            className="text-muted-foreground"
            title="No generator declared: this course is outside anything measured at generator grain (ADR-0024)."
          >
            unknown
          </span>
        )}
      </TableCell>
      <TableCell>
        {course.consumable_url ? (
          <a
            href={course.consumable_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            Open <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : (
          <span
            className="text-xs text-muted-foreground"
            title="No deployed instance declared: this course can be evaluated automatically, but not by a human. Declare one in Courses."
          >
            none
          </span>
        )}
      </TableCell>
    </TableRow>
  );
}

/** One version, with what entered and what left since the one before it. Selecting it is what
 *  makes an older membership readable — a campaign may still be running on one. */
function VersionRow({
  version,
  diff,
  isLatest,
  isSelected,
  onSelect,
  courseName,
}: {
  version: DatasetVersionResponse;
  diff: MembershipDiff;
  isLatest: boolean;
  isSelected: boolean;
  onSelect: () => void;
  courseName: (id: Uuid) => string;
}) {
  const isFirst = version.ordinal === 1;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={isSelected}
      className={cn(
        "w-full rounded-md border p-3 text-left transition-colors hover:bg-accent",
        isSelected ? "border-primary bg-accent/50" : null,
      )}
    >
      <div className="flex items-center gap-2">
        <Badge variant={isLatest ? "success" : "secondary"}>v{version.ordinal}</Badge>
        <span className="text-sm font-medium">{version.note}</span>
        <span className="ml-auto text-xs text-muted-foreground">
          {version.content_ids.length} courses
        </span>
      </div>

      <div className="mt-2 space-y-1 text-xs">
        {isFirst ? (
          // A first version is a set arriving, not a set changing: listing every course as
          // "added" would read as a change against something that never existed.
          <p className="text-muted-foreground">The set as it was first frozen.</p>
        ) : (
          <>
            {diff.added.length ? (
              <p className="text-muted-foreground">
                <span className="font-medium text-foreground">+{diff.added.length}</span>{" "}
                {diff.added.map(courseName).join(", ")}
              </p>
            ) : null}
            {diff.removed.length ? (
              <p className="text-muted-foreground">
                <span className="font-medium text-foreground">−{diff.removed.length}</span>{" "}
                {diff.removed.map(courseName).join(", ")}
              </p>
            ) : null}
          </>
        )}
      </div>
    </button>
  );
}
