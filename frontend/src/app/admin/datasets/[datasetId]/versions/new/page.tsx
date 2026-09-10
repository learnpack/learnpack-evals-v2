"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { DatasetVersionForm } from "@/components/admin/dataset-version-form";
import { useDataset } from "@/lib/api/hooks";
import { latestVersion } from "@/lib/datasets";

export default function NewDatasetVersionPage({
  params,
}: {
  params: Promise<{ datasetId: string }>;
}) {
  const { datasetId } = use(params);
  const { data: dataset, isLoading, error } = useDataset(datasetId);

  // The form is mounted only past these: it reads the current membership once, into state.
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!dataset) return <ErrorState message="Dataset not found." />;

  const current = latestVersion(dataset);

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <Link
          href={`/admin/datasets/${dataset.dataset_id}`}
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> {dataset.name}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">
          Freeze v{(current?.ordinal ?? 0) + 1} of {dataset.name}
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          It starts from v{current?.ordinal ?? "?"}: what is in the set when you freeze it is
          the whole membership of the new version, not what is being added. Once frozen, it is
          immutable.
        </p>
      </div>

      <DatasetVersionForm dataset={dataset} />
    </div>
  );
}
