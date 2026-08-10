"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { FileText, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useCreateGenerator,
  useCreateGeneratorVersion,
  useGenerators,
  useGeneratorVersions,
} from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { GeneratorResponse, GeneratorVersionResponse } from "@/lib/api/types";

/** The one key this console writes into the identity blob (ADR-0030 §2). */
const CHANGELOG_KEY = "changelog";

export default function GeneratorsPage() {
  const { data: generators, isLoading, error } = useGenerators();
  const { data: versions } = useGeneratorVersions();
  const [creating, setCreating] = useState(false);
  const [addingVersionTo, setAddingVersionTo] = useState<GeneratorResponse | null>(null);
  const [detailsFor, setDetailsFor] = useState<GeneratorVersionResponse | null>(null);

  const versionsByGenerator = useMemo(() => {
    const grouped = new Map<string, GeneratorVersionResponse[]>();
    for (const version of versions ?? []) {
      grouped.set(version.generator_id, [...(grouped.get(version.generator_id) ?? []), version]);
    }
    return grouped;
  }, [versions]);

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Generators</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            The examinee, in two grains: a generator, and the versions registered under it. A
            version is immutable — a different one is a new registration, never an edit.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> Register generator
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !generators || generators.length === 0 ? (
        <EmptyState
          title="No generators yet"
          hint="Register the generator behind your content, then a version under it, to accumulate claims against it."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Version</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {generators.map((generator) => {
                  const owned = versionsByGenerator.get(generator.generator_id) ?? [];
                  return [
                    // The lineage heads its own versions: the shape of the table is what
                    // teaches the two grains apart.
                    <TableRow key={generator.generator_id} className="bg-muted/40">
                      <TableCell className="font-medium">{generator.name}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setAddingVersionTo(generator)}
                        >
                          <Plus className="h-3.5 w-3.5" /> Add version
                        </Button>
                      </TableCell>
                    </TableRow>,
                    ...(owned.length === 0
                      ? [
                          <TableRow key={`${generator.generator_id}-empty`}>
                            <TableCell colSpan={2} className="pl-8 text-sm text-muted-foreground">
                              No version registered yet — content cannot declare this generator
                              until one exists.
                            </TableCell>
                          </TableRow>,
                        ]
                      : owned.map((version) => (
                          <TableRow key={version.generator_version_id}>
                            <TableCell className="pl-8">{version.version}</TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setDetailsFor(version)}
                              >
                                <FileText className="h-3.5 w-3.5" /> Details
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))),
                  ];
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="Register a generator"
        description="The name is typed here and nowhere else — every version selects it afterwards."
      >
        <GeneratorForm onDone={() => setCreating(false)} />
      </Dialog>

      <Dialog
        open={addingVersionTo !== null}
        onClose={() => setAddingVersionTo(null)}
        title="Register a version"
        description={addingVersionTo ? `Under ${addingVersionTo.name}.` : undefined}
      >
        {addingVersionTo ? (
          <GeneratorVersionForm
            generator={addingVersionTo}
            onDone={() => setAddingVersionTo(null)}
          />
        ) : null}
      </Dialog>

      <Dialog
        open={detailsFor !== null}
        onClose={() => setDetailsFor(null)}
        title="Version details"
        description={detailsFor ? `${detailsFor.name} ${detailsFor.version}` : undefined}
      >
        {detailsFor ? <GeneratorDetails version={detailsFor} /> : null}
      </Dialog>
    </div>
  );
}

function GeneratorForm({ onDone }: { onDone: () => void }) {
  const createGenerator = useCreateGenerator();
  const [name, setName] = useState("");
  /** The registered name a near-miss refusal named. Held so "Register it anyway" can echo it
   *  back — the override has to prove this specific answer was read (ADR-0031 §4). */
  const [nearMiss, setNearMiss] = useState<string | null>(null);

  function submit(confirmDistinctFrom?: string) {
    createGenerator.mutate(
      { name: name.trim(), ...(confirmDistinctFrom ? { confirm_distinct_from: confirmDistinctFrom } : {}) },
      {
        onSuccess: () => {
          toast.success("Generator registered.");
          onDone();
        },
        onError: (err) => {
          const apiError = err as ApiError;
          if (apiError.status === 409) {
            // Two different 409s: the same lineage, or a question about a similar one. Only
            // the second is answerable, and it carries the name to echo back.
            const named = apiError.data?.similarTo;
            setNearMiss(typeof named === "string" ? named : null);
            toast.error(
              named ? "That looks like a typo." : "A generator with that name is already registered.",
              { description: apiError.message },
            );
          } else {
            toast.error("Could not register the generator.", { description: apiError.message });
          }
        },
      },
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <div className="space-y-1.5">
        <Label>
          Name <span className="text-destructive">*</span>
        </Label>
        <Input
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setNearMiss(null);
          }}
          placeholder="learnpack-generator"
          required
        />
        <p className="text-xs text-muted-foreground">
          A name one or two edits from a registered one is refused: that is what stops a version
          of one generator being recorded as another.
        </p>
      </div>

      {nearMiss ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
          <p>
            This is very close to <span className="font-medium">{nearMiss}</span>. If it really is
            a different generator, say so — the claims of the two will never be pooled.
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            disabled={createGenerator.isPending}
            onClick={() => submit(nearMiss)}
          >
            It is not {nearMiss} — register it
          </Button>
        </div>
      ) : null}

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={createGenerator.isPending}>
          {createGenerator.isPending ? <Spinner /> : null}
          Register
        </Button>
      </div>
    </form>
  );
}

function GeneratorVersionForm({
  generator,
  onDone,
}: {
  generator: GeneratorResponse;
  onDone: () => void;
}) {
  const createVersion = useCreateGeneratorVersion();
  const [version, setVersion] = useState("");
  const [changelog, setChangelog] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const note = changelog.trim();
    createVersion.mutate(
      {
        generatorId: generator.generator_id,
        body: {
          version: version.trim(),
          // An empty field declares nothing — it must not write an empty key into the blob.
          ...(note ? { metadata: { [CHANGELOG_KEY]: note } } : {}),
        },
      },
      {
        onSuccess: () => {
          toast.success("Version registered.");
          onDone();
        },
        onError: (err) => {
          const apiError = err as ApiError;
          if (apiError.status === 409) {
            toast.error(`${generator.name} already has that version.`);
          } else {
            toast.error("Could not register the version.", { description: apiError.message });
          }
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label>
          Version <span className="text-destructive">*</span>
        </Label>
        <Input
          value={version}
          onChange={(e) => setVersion(e.target.value)}
          placeholder="2.4.0"
          required
        />
      </div>
      <div className="space-y-1.5">
        <Label>Changelog</Label>
        <Textarea
          value={changelog}
          onChange={(e) => setChangelog(e.target.value)}
          placeholder="What changed in this version, in a sentence or two."
        />
        <p className="text-xs text-muted-foreground">
          Optional reference for whoever reads the results. It cannot be edited afterwards — the
          declared identity is immutable.
        </p>
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={createVersion.isPending}>
          {createVersion.isPending ? <Spinner /> : null}
          Register
        </Button>
      </div>
    </form>
  );
}

/** Read-only. The form writes `changelog` and nothing else, but the endpoint accepts any
 *  metadata (the seeder and API clients use it), so whatever is stored is rendered. */
function GeneratorDetails({ version }: { version: GeneratorVersionResponse }) {
  const { [CHANGELOG_KEY]: changelog, ...rest } = version.metadata ?? {};
  const otherKeys = Object.keys(rest);

  return (
    <div className="space-y-4 text-sm">
      <div className="space-y-1">
        <h3 className="font-medium">Changelog</h3>
        {typeof changelog === "string" && changelog.trim() ? (
          <p className="whitespace-pre-wrap text-muted-foreground">{changelog}</p>
        ) : (
          <p className="text-muted-foreground">None declared for this version.</p>
        )}
      </div>

      <div className="space-y-1">
        <h3 className="font-medium">Other metadata</h3>
        {otherKeys.length === 0 ? (
          <p className="text-muted-foreground">None.</p>
        ) : (
          <ul className="space-y-1">
            {otherKeys.map((key) => (
              <li key={key}>
                <span className="font-medium">{key}</span>{" "}
                <span className="text-muted-foreground">
                  {typeof rest[key] === "string" ? String(rest[key]) : JSON.stringify(rest[key])}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
