"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Pencil, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { DatasetVersionForm } from "@/components/admin/dataset-version-form";
import { RenameDatasetForm } from "@/components/admin/rename-dataset-form";
import { useContents, useDataset } from "@/lib/api/hooks";
import { latestVersion, versionHistory, type MembershipDiff } from "@/lib/datasets";
import type { DatasetVersionResponse, Uuid } from "@/lib/api/types";

export default function DatasetPage({ params }: { params: Promise<{ datasetId: string }> }) {
  const { datasetId } = use(params);
  const { data: dataset, isLoading, error } = useDataset(datasetId);
  const { data: courses } = useContents();

  const [renaming, setRenaming] = useState(false);
  const [versioning, setVersioning] = useState(false);

  const courseName = useMemo(() => {
    const byId = new Map((courses ?? []).map((c) => [c.content_id, c.external_id]));
    return (id: Uuid) => byId.get(id) ?? id.slice(0, 8);
  }, [courses]);

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!dataset) return <ErrorState message="Dataset not found." />;

  const latest = latestVersion(dataset);
  const history = versionHistory(dataset);

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
              courseName={courseName}
            />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Courses in v{latest?.ordinal ?? "?"}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-1 text-sm sm:grid-cols-2">
            {(latest?.content_ids ?? []).map((id) => (
              <li key={id} className="truncate text-muted-foreground">
                {courseName(id)}
              </li>
            ))}
          </ul>
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

/** One version, with what entered and what left since the one before it. */
function VersionRow({
  version,
  diff,
  isLatest,
  courseName,
}: {
  version: DatasetVersionResponse;
  diff: MembershipDiff;
  isLatest: boolean;
  courseName: (id: Uuid) => string;
}) {
  const isFirst = version.ordinal === 1;
  return (
    <div className="rounded-md border p-3">
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
    </div>
  );
}
