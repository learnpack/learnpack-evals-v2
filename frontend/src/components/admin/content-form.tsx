"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { useBriefs, useCreateContent, useGenerators } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { PACKAGE_FORMAT } from "@/lib/constants";
import type { EditProvenance } from "@/lib/api/types";

type ArtifactRow = { kind: string; locator: string };

// No metadata fields on purpose (ADR-0017): whatever the platform declares travels as
// package artifacts; hand-typed declarations would contaminate the evaluated surface.
export function ContentForm({ onDone }: { onDone: () => void }) {
  const createContent = useCreateContent();
  const { data: briefs } = useBriefs();
  const { data: generators } = useGenerators();

  const [externalId, setExternalId] = useState("");
  const [consumableUrl, setConsumableUrl] = useState("");
  const [version, setVersion] = useState("");
  const [briefId, setBriefId] = useState("");
  const [generatorVersionId, setGeneratorVersionId] = useState("");
  const [editProvenance, setEditProvenance] = useState<EditProvenance>("unknown");
  const [artifacts, setArtifacts] = useState<ArtifactRow[]>([]);

  const pending = createContent.isPending;

  function reportError(err: unknown) {
    const e = err as ApiError;
    if (e.status === 409) {
      toast.error("A course with that id and version already exists.");
    } else {
      toast.error("Could not save the course.", { description: e.message });
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    createContent.mutate(
      {
        package_format: PACKAGE_FORMAT,
        external_id: externalId.trim(),
        consumable_url: consumableUrl.trim(),
        ...(version.trim() ? { version: version.trim() } : {}),
        artifacts: artifacts
          .filter((a) => a.kind.trim() && a.locator.trim())
          .map((a) => ({ kind: a.kind.trim(), locator: a.locator.trim() })),
        brief_id: briefId || null,
        generator_version_id: generatorVersionId || null,
        edit_provenance: editProvenance,
      },
      {
        onSuccess: () => {
          toast.success("Course registered.");
          onDone();
        },
        onError: reportError,
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Course id (external_id)" required>
        <Input
          value={externalId}
          onChange={(e) => setExternalId(e.target.value)}
          placeholder="introduction-to-generative-ai"
          required
        />
      </Field>
      <Field label="Consumable URL" required>
        <Input
          type="url"
          value={consumableUrl}
          onChange={(e) => setConsumableUrl(e.target.value)}
          placeholder="https://introduction-to-generative-ai.learn-pack.com/"
          required
        />
      </Field>
      <Field label="Version" hint="Optional — defaults to 1.">
        <Input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="1" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Generator" hint="Optional — unknown if omitted.">
          <Select
            value={generatorVersionId}
            onChange={(e) => setGeneratorVersionId(e.target.value)}
          >
            <option value="">Unknown</option>
            {(generators ?? []).map((g) => (
              <option key={g.generator_version_id} value={g.generator_version_id}>
                {g.name} {g.version}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Brief" hint="Optional.">
          <Select value={briefId} onChange={(e) => setBriefId(e.target.value)}>
            <option value="">None recorded</option>
            {(briefs ?? []).map((b) => (
              <option key={b.brief_id} value={b.brief_id}>
                {b.brief.slice(0, 60)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
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
      <Field
        label="Package artifacts"
        hint="Optional — manifests, item banks… the best evidence for extraction."
      >
        <div className="space-y-2">
          {artifacts.map((artifact, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={artifact.kind}
                onChange={(e) =>
                  setArtifacts(
                    artifacts.map((a, i) => (i === index ? { ...a, kind: e.target.value } : a)),
                  )
                }
                placeholder="manifest"
                className="w-40"
              />
              <Input
                value={artifact.locator}
                onChange={(e) =>
                  setArtifacts(
                    artifacts.map((a, i) =>
                      i === index ? { ...a, locator: e.target.value } : a,
                    ),
                  )
                }
                placeholder="https://…/learn.json"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setArtifacts(artifacts.filter((_, i) => i !== index))}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setArtifacts([...artifacts, { kind: "", locator: "" }])}
          >
            Add artifact
          </Button>
        </div>
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
