"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Package, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useCreateGenerator,
  useCreateGeneratorArtifact,
  useGeneratorArtifacts,
  useGenerators,
} from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { GeneratorVersionResponse } from "@/lib/api/types";

export default function GeneratorsPage() {
  const { data: generators, isLoading, error } = useGenerators();
  const [creating, setCreating] = useState(false);
  const [artifactsFor, setArtifactsFor] = useState<GeneratorVersionResponse | null>(null);

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
                      <Button variant="ghost" size="sm" onClick={() => setArtifactsFor(g)}>
                        <Package className="h-3.5 w-3.5" /> Artifacts
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
        open={artifactsFor !== null}
        onClose={() => setArtifactsFor(null)}
        title="Generator artifacts"
        description={
          artifactsFor ? `${artifactsFor.name} ${artifactsFor.version}` : undefined
        }
      >
        {artifactsFor ? <ArtifactsPanel generator={artifactsFor} /> : null}
      </Dialog>
    </div>
  );
}

function GeneratorForm({ onDone }: { onDone: () => void }) {
  const createGenerator = useCreateGenerator();
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    createGenerator.mutate(
      { name: name.trim(), version: version.trim() },
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

function ArtifactsPanel({ generator }: { generator: GeneratorVersionResponse }) {
  const { data: artifacts, isLoading } = useGeneratorArtifacts(generator.generator_version_id);
  const createArtifact = useCreateGeneratorArtifact(generator.generator_version_id);
  const [kind, setKind] = useState("");
  const [locator, setLocator] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    createArtifact.mutate(
      { kind: kind.trim(), locator: locator.trim() },
      {
        onSuccess: () => {
          toast.success("Artifact registered.");
          setKind("");
          setLocator("");
        },
        onError: (err) =>
          toast.error("Could not register the artifact.", {
            description: (err as ApiError).message,
          }),
      },
    );
  }

  return (
    <div className="space-y-4">
      {isLoading ? (
        <LoadingState />
      ) : !artifacts || artifacts.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No artifacts yet. Registered now, profiled when a claim needs them.
        </p>
      ) : (
        <ul className="space-y-1 text-sm">
          {artifacts.map((a) => (
            <li key={a.artifact_id}>
              <span className="font-medium">{a.kind}</span>{" "}
              <span className="text-muted-foreground">{a.locator}</span>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="flex items-end gap-2">
        <div className="flex-1 space-y-1.5">
          <Label>Kind</Label>
          <Input
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            placeholder="prompt-template"
            required
          />
        </div>
        <div className="flex-[2] space-y-1.5">
          <Label>Locator</Label>
          <Input
            value={locator}
            onChange={(e) => setLocator(e.target.value)}
            placeholder="https://…"
            required
          />
        </div>
        <Button type="submit" disabled={createArtifact.isPending}>
          Add
        </Button>
      </form>
    </div>
  );
}
