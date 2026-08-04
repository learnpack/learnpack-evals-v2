"use client";

import { useState } from "react";
import { ExternalLink, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ContentForm } from "@/components/admin/content-form";
import { useContents } from "@/lib/api/hooks";
import type { ContentResponse } from "@/lib/api/types";

export default function ContentsPage() {
  const { data: contents, isLoading, error } = useContents();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ContentResponse | null>(null);

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
                  <TableHead>URL</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contents.map((c) => (
                  <TableRow key={c.content_id}>
                    <TableCell className="font-medium">{c.external_id}</TableCell>
                    <TableCell>{c.version}</TableCell>
                    <TableCell className="text-muted-foreground">{c.package_format}</TableCell>
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
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(c)}>
                        <Pencil className="h-3.5 w-3.5" /> Metadata
                      </Button>
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
        description="Manually add an AI-generated course and its LearnpackV1 metadata."
      >
        <ContentForm mode="create" onDone={() => setCreating(false)} />
      </Dialog>

      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title="Edit metadata"
        description={editing ? `Course ${editing.external_id}` : undefined}
      >
        {editing ? (
          <ContentForm mode="edit" content={editing} onDone={() => setEditing(null)} />
        ) : null}
      </Dialog>
    </div>
  );
}
