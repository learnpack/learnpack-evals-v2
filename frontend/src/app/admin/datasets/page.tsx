"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DatasetForm } from "@/components/admin/dataset-form";
import { useDatasets } from "@/lib/api/hooks";
import { latestVersion } from "@/lib/datasets";

export default function DatasetsPage() {
  const { data: datasets, isLoading, error } = useDatasets();
  const [creating, setCreating] = useState(false);

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Datasets</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            A named set of courses, reusable across rounds. Its membership is frozen into
            versions, so two rounds can say whether they ran on the same one.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> New dataset
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !datasets || datasets.length === 0 ? (
        <EmptyState
          title="No datasets yet"
          hint="Declare one to reuse the same courses across campaigns."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Dataset</TableHead>
                  <TableHead>Courses</TableHead>
                  <TableHead>At</TableHead>
                  <TableHead>Latest change</TableHead>
                  <TableHead className="text-right">Manage</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {datasets.map((dataset) => {
                  const latest = latestVersion(dataset);
                  return (
                    <TableRow key={dataset.dataset_id}>
                      <TableCell>
                        <div className="font-medium">{dataset.name}</div>
                        {dataset.description ? (
                          <div className="max-w-md truncate text-xs text-muted-foreground">
                            {dataset.description}
                          </div>
                        ) : null}
                      </TableCell>
                      <TableCell>{latest?.content_ids.length ?? 0}</TableCell>
                      <TableCell>
                        <Badge variant="outline">v{latest?.ordinal ?? "?"}</Badge>
                      </TableCell>
                      <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                        {latest?.note ?? "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link
                          href={`/admin/datasets/${dataset.dataset_id}`}
                          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                        >
                          Open <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="Declare a dataset"
        description="Name the set and pick its courses. Declaring it freezes its first version."
        className="max-w-4xl"
      >
        <DatasetForm onDone={() => setCreating(false)} />
      </Dialog>
    </div>
  );
}
