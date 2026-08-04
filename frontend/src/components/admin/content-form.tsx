"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { useCreateContent, useUpdateContentMetadata } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { PACKAGE_FORMAT } from "@/lib/constants";
import type { ContentResponse, MetadataEntry } from "@/lib/api/types";

const linesToList = (v: string) =>
  v
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);

function metadataFromEntries(entries: MetadataEntry[]) {
  const byKey = Object.fromEntries(entries.map((e) => [e.key, e.value]));
  return {
    learningObjectives: Array.isArray(byKey.learningObjectives)
      ? byKey.learningObjectives.join("\n")
      : "",
    targetAudience: typeof byKey.targetAudience === "string" ? byKey.targetAudience : "",
    prerequisites: Array.isArray(byKey.prerequisites) ? byKey.prerequisites.join("\n") : "",
  };
}

function buildMetadata(values: {
  learningObjectives: string;
  targetAudience: string;
  prerequisites: string;
}): Record<string, unknown> {
  const metadata: Record<string, unknown> = {
    learningObjectives: linesToList(values.learningObjectives),
    targetAudience: values.targetAudience.trim(),
  };
  const prereq = linesToList(values.prerequisites);
  if (prereq.length) metadata.prerequisites = prereq;
  return metadata;
}

export function ContentForm({
  mode,
  content,
  onDone,
}: {
  mode: "create" | "edit";
  content?: ContentResponse;
  onDone: () => void;
}) {
  const createContent = useCreateContent();
  const updateMetadata = useUpdateContentMetadata();

  const [externalId, setExternalId] = useState(content?.external_id ?? "");
  const [consumableUrl, setConsumableUrl] = useState(content?.consumable_url ?? "");
  const [version, setVersion] = useState(content?.version ?? "");
  const initialMeta = content ? metadataFromEntries(content.metadata) : null;
  const [learningObjectives, setLearningObjectives] = useState(
    initialMeta?.learningObjectives ?? "",
  );
  const [targetAudience, setTargetAudience] = useState(initialMeta?.targetAudience ?? "");
  const [prerequisites, setPrerequisites] = useState(initialMeta?.prerequisites ?? "");

  const pending = createContent.isPending || updateMetadata.isPending;

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
    const metadata = buildMetadata({ learningObjectives, targetAudience, prerequisites });

    if (mode === "edit" && content) {
      updateMetadata.mutate(
        { id: content.content_id, metadata },
        {
          onSuccess: () => {
            toast.success("Metadata updated.");
            onDone();
          },
          onError: reportError,
        },
      );
      return;
    }

    createContent.mutate(
      {
        package_format: PACKAGE_FORMAT,
        external_id: externalId.trim(),
        consumable_url: consumableUrl.trim(),
        ...(version.trim() ? { version: version.trim() } : {}),
        metadata,
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
      {mode === "create" ? (
        <>
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
        </>
      ) : null}

      <Field label="Learning objectives" hint="One per line." required>
        <Textarea
          value={learningObjectives}
          onChange={(e) => setLearningObjectives(e.target.value)}
          rows={4}
          placeholder={"Explain how a transformer works\nBuild a simple chatbot"}
          required
        />
      </Field>
      <Field label="Target audience" required>
        <Input
          value={targetAudience}
          onChange={(e) => setTargetAudience(e.target.value)}
          placeholder="Junior developers new to AI"
          required
        />
      </Field>
      <Field label="Prerequisites" hint="One per line — optional.">
        <Textarea
          value={prerequisites}
          onChange={(e) => setPrerequisites(e.target.value)}
          rows={3}
          placeholder={"Basic Python\nFamiliarity with the command line"}
        />
      </Field>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onDone} disabled={pending}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Spinner /> : null}
          {mode === "create" ? "Register course" : "Save metadata"}
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
        {hint ? <span className="ml-2 font-normal text-muted-foreground">{hint}</span> : null}
      </Label>
      {children}
    </div>
  );
}
