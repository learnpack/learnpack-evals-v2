"use client";

import { useState } from "react";
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
import { useCreateGenerator, useGenerators } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { GeneratorVersionResponse } from "@/lib/api/types";

/** The one key this console writes into the identity blob (ADR-0030 §2). */
const CHANGELOG_KEY = "changelog";

export default function GeneratorsPage() {
  const { data: generators, isLoading, error } = useGenerators();
  const [creating, setCreating] = useState(false);
  const [detailsFor, setDetailsFor] = useState<GeneratorVersionResponse | null>(null);

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Generators</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Declared generator versions — the examinee. A different generator is a new
            registration, never an edit.
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
          hint="Register the generator version behind your content to accumulate claims against it."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {generators.map((g) => (
                  <TableRow key={g.generator_version_id}>
                    <TableCell className="font-medium">{g.name}</TableCell>
                    <TableCell>{g.version}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => setDetailsFor(g)}>
                        <FileText className="h-3.5 w-3.5" /> Details
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
        title="Register a generator version"
        description="The declared identity claims will accumulate against."
      >
        <GeneratorForm onDone={() => setCreating(false)} />
      </Dialog>

      <Dialog
        open={detailsFor !== null}
        onClose={() => setDetailsFor(null)}
        title="Generator details"
        description={detailsFor ? `${detailsFor.name} ${detailsFor.version}` : undefined}
      >
        {detailsFor ? <GeneratorDetails generator={detailsFor} /> : null}
      </Dialog>
    </div>
  );
}

function GeneratorForm({ onDone }: { onDone: () => void }) {
  const createGenerator = useCreateGenerator();
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");
  const [changelog, setChangelog] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const note = changelog.trim();
    createGenerator.mutate(
      {
        name: name.trim(),
        version: version.trim(),
        // An empty field declares nothing — it must not write an empty key into the blob.
        ...(note ? { metadata: { [CHANGELOG_KEY]: note } } : {}),
      },
      {
        onSuccess: () => {
          toast.success("Generator registered.");
          onDone();
        },
        onError: (err) => {
          const apiError = err as ApiError;
          if (apiError.status === 409) {
            toast.error("That generator name and version is already registered.");
          } else {
            toast.error("Could not register the generator.", { description: apiError.message });
          }
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label>
          Name <span className="text-destructive">*</span>
        </Label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="learnpack-generator"
          required
        />
      </div>
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
        <Button type="submit" disabled={createGenerator.isPending}>
          {createGenerator.isPending ? <Spinner /> : null}
          Register
        </Button>
      </div>
    </form>
  );
}

/** Read-only. The form writes `changelog` and nothing else, but the endpoint accepts any
 *  metadata (the seeder and API clients use it), so whatever is stored is rendered. */
function GeneratorDetails({ generator }: { generator: GeneratorVersionResponse }) {
  const { [CHANGELOG_KEY]: changelog, ...rest } = generator.metadata ?? {};
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
