"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ContentForm } from "@/components/admin/content-form";
import { useBriefs, useContents, useGenerators } from "@/lib/api/hooks";
import type { GeneratorVersionResponse } from "@/lib/api/types";

const generatorName = (g?: GeneratorVersionResponse) => (g ? `${g.name} ${g.version}` : undefined);

export default function ContentsPage() {
  const { data: contents, isLoading, error } = useContents();
  // Brief and generator travel as ids on the content: resolved here so the two facts
  // that decide what a study can do with a course are readable — which commission it
  // shares (the pairing key) and whether its generator is known.
  const { data: briefs } = useBriefs();
  const { data: generators } = useGenerators();
  const [creating, setCreating] = useState(false);

  const briefById = useMemo(() => new Map((briefs ?? []).map((b) => [b.brief_id, b])), [briefs]);
  const generatorById = useMemo(
    () => new Map((generators ?? []).map((g) => [g.generator_version_id, g])),
    [generators],
  );

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Courses</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            AI-generated courses available to evaluate.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> Add course
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !contents || contents.length === 0 ? (
        <EmptyState title="No courses yet" hint="Add your first course to start a campaign." />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Course</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Format</TableHead>
                  <TableHead>Brief</TableHead>
                  <TableHead>Generator</TableHead>
                  <TableHead>URL</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contents.map((c) => (
                  <TableRow key={c.content_id}>
                    <TableCell className="font-medium">{c.external_id}</TableCell>
                    <TableCell>{c.version}</TableCell>
                    <TableCell className="text-muted-foreground">{c.package_format}</TableCell>
                    <TableCell className="max-w-xs">
                      {c.brief_id ? (
                        <span className="line-clamp-2 text-xs" title={c.brief_id}>
                          {briefById.get(c.brief_id)?.brief ?? c.brief_id}
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
                      {c.generator_version_id ? (
                        <span title={c.generator_version_id}>
                          {generatorName(generatorById.get(c.generator_version_id)) ??
                            c.generator_version_id}
                        </span>
                      ) : (
                        <span
                          className="text-muted-foreground"
                          title="Unknown generator: excluded from generator-level accumulation in study reports."
                        >
                          unknown
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <a
                        href={c.consumable_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        Open <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="Register a course"
        description="Manually add an AI-generated course and its package artifacts."
      >
        <ContentForm onDone={() => setCreating(false)} />
      </Dialog>
    </div>
  );
}
