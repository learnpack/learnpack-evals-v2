"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { ContentForm } from "@/components/admin/content-form";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import {
  useAttributeGenerator,
  useBriefs,
  useContents,
  useGeneratorVersions,
} from "@/lib/api/hooks";
import type { ContentResponse, GeneratorVersionResponse } from "@/lib/api/types";

const generatorName = (g?: GeneratorVersionResponse) => (g ? `${g.name} ${g.version}` : undefined);

export default function ContentsPage() {
  const { data: contents, isLoading, error } = useContents();
  // Brief and generator travel as ids on the content: resolved here so the two facts
  // that decide what a study can do with a course are readable — which commission it
  // shares (the pairing key) and whether its generator is known.
  const { data: briefs } = useBriefs();
  const { data: generators } = useGeneratorVersions();
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
                        <span
                          title={
                            c.generator_attributed_at
                              ? `${c.generator_version_id} — attributed after registration on ${new Date(c.generator_attributed_at).toLocaleDateString()}`
                              : c.generator_version_id
                          }
                        >
                          {generatorName(generatorById.get(c.generator_version_id)) ??
                            c.generator_version_id}
                          {c.generator_attributed_at ? (
                            <span className="ml-1 text-muted-foreground">(attributed later)</span>
                          ) : null}
                        </span>
                      ) : (
                        <AttributeGeneratorCell content={c} generators={generators ?? []} />
                      )}
                    </TableCell>
                    <TableCell>
                      {c.consumable_url ? (
                        <a
                          href={c.consumable_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-primary hover:underline"
                        >
                          Open <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                      ) : (
                        <span
                          className="text-xs text-muted-foreground"
                          title="No deployed instance declared: this course can be evaluated automatically, but not by a human."
                        >
                          none
                        </span>
                      )}
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

/** An unknown generator is a declared void — and the one thing that can still be filled,
 *  once (ADR-0024). Everything else about a registered content stays immutable. */
function AttributeGeneratorCell({
  content,
  generators,
}: {
  content: ContentResponse;
  generators: GeneratorVersionResponse[];
}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState("");
  const attribute = useAttributeGenerator();

  function submit() {
    attribute.mutate(
      { contentId: content.content_id, body: { generator_version_id: selected } },
      {
        onSuccess: () => {
          setOpen(false);
          toast.success("Generator attributed.");
        },
        onError: (err) => {
          const e = err as ApiError;
          setOpen(false);
          if (e.status === 409) {
            toast.error("This course already has a generator — attribution never replaces one.");
          } else {
            toast.error("Could not attribute.", { description: e.message });
          }
        },
      },
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
        title="Declared unknown: excluded from generator-level accumulation. Attribute one if you learn it."
      >
        unknown
      </button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={`Attribute a generator to ${content.external_id}`}
        description="Records a generator learnt after registration. It fills the declared unknown once and cannot be changed afterwards."
      >
        {generators.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No generator version registered yet — register one first in /admin/generators.
          </p>
        ) : (
          <Select value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="" disabled>
              Choose…
            </option>
            {[...new Map(generators.map((g) => [g.name, g] as const)).keys()].map((name) => (
              <optgroup key={name} label={name}>
                {generators
                  .filter((g) => g.name === name)
                  .map((g) => (
                    <option key={g.generator_version_id} value={g.generator_version_id}>
                      {g.version}
                    </option>
                  ))}
              </optgroup>
            ))}
          </Select>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)} disabled={attribute.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!selected || attribute.isPending}>
            {attribute.isPending ? <Spinner /> : null} Attribute
          </Button>
        </div>
      </Dialog>
    </>
  );
}
