"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { useGenerators, usePackageFormats, useRegisterBySource } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { EditProvenance } from "@/lib/api/types";

/** The declared "no generator" option — distinct from the unchosen placeholder (ADR-0024). */
const UNKNOWN_GENERATOR = "unknown";

// Registration by discovery (ADR-0027): the form declares a source, never an artifact
// list — identity, artifacts and content hash come from the package itself. And no
// metadata fields (ADR-0017): hand-typed declarations would contaminate the evaluated
// surface.
export function ContentForm({ onDone }: { onDone: () => void }) {
  const registerBySource = useRegisterBySource();
  const { data: formats } = usePackageFormats();
  const { data: generators } = useGenerators();

  const [sourceLocator, setSourceLocator] = useState("");
  const [packageFormat, setPackageFormat] = useState("");
  const [version, setVersion] = useState("");
  const [generatorVersionId, setGeneratorVersionId] = useState("");
  const [editProvenance, setEditProvenance] = useState<EditProvenance>("unknown");

  // A single supported format needs no choice — preselect it, keep the select visible.
  useEffect(() => {
    if (!packageFormat && formats?.length === 1) setPackageFormat(formats[0]);
  }, [formats, packageFormat]);

  const pending = registerBySource.isPending;

  function reportError(err: unknown) {
    const e = err as ApiError;
    if (e.status === 409) {
      toast.error("Already registered at that version with different content.", {
        description: e.message,
      });
    } else {
      toast.error("Could not register the course.", { description: e.message });
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    registerBySource.mutate(
      {
        package_format: packageFormat,
        source_locator: sourceLocator.trim(),
        ...(version.trim() ? { version: version.trim() } : {}),
        // Three states, not two (ADR-0024): the placeholder never reaches here because the
        // select is required; "unknown" is a declaration, and it is not the same as silence.
        generator_version_id: generatorVersionId === UNKNOWN_GENERATOR ? null : generatorVersionId,
        edit_provenance: editProvenance,
      },
      {
        onSuccess: (result) => {
          if (result.created) {
            toast.success(
              `Course registered — ${result.artifact_count} artifacts discovered.`,
            );
          } else {
            toast.info("Already registered — the package content is unchanged.");
          }
          onDone();
        },
        onError: reportError,
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field
        label="Package URL"
        required
        hint="The course's base URL. Its identity, artifact list and content hash are discovered from the package itself."
      >
        <Input
          type="url"
          value={sourceLocator}
          onChange={(e) => setSourceLocator(e.target.value)}
          placeholder="https://introduction-to-generative-ai.learn-pack.com"
          required
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Package format" required>
          <Select
            value={packageFormat}
            onChange={(e) => setPackageFormat(e.target.value)}
            required
          >
            <option value="" disabled>
              Choose…
            </option>
            {(formats ?? []).map((format) => (
              <option key={format} value={format}>
                {format}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Version" hint="Optional — defaults to 1.">
          <Input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="1" />
        </Field>
      </div>
      <Field
        label="Generator"
        required
        hint={
          (generators ?? []).length === 0
            ? "No generator registered yet — declare unknown, or register one first."
            : "Unknown is a valid answer, but it must be chosen: content with an unknown generator stays out of generator-level accumulation."
        }
      >
        <Select
          value={generatorVersionId}
          onChange={(e) => setGeneratorVersionId(e.target.value)}
          required
        >
          <option value="" disabled>
            Choose…
          </option>
          <option value={UNKNOWN_GENERATOR}>Unknown — cannot be attributed</option>
          {(generators ?? []).map((g) => (
            <option key={g.generator_version_id} value={g.generator_version_id}>
              {g.name} {g.version}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Edit provenance" hint="Was the generator output edited by a human?">
        <Select
          value={editProvenance}
          onChange={(e) => setEditProvenance(e.target.value as EditProvenance)}
        >
          <option value="unknown">Unknown</option>
          <option value="pure">Pure generator output</option>
          <option value="human_edited">Human edited</option>
        </Select>
      </Field>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onDone} disabled={pending}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner /> : null}
          Register course
        </Button>
      </div>
    </form>
  );
}

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label} {required ? <span className="text-destructive">*</span> : null}
      </Label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
