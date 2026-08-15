"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { useCreateGeneratorVersion } from "@/lib/api/hooks";
import type { ApiError } from "@/lib/api/client";
import type { Uuid } from "@/lib/api/types";

/** The one key the console writes into the identity blob (ADR-0030 §2). */
export const CHANGELOG_KEY = "changelog";

/**
 * Registering a version, from wherever one is being asked for.
 *
 * A version is what changes often — a lineage is not — so this is the act that must never
 * cost a trip to another screen. The lineage itself is deliberately not creatable here: a
 * new generator is rare, and the near-miss refusal that stops a typo becoming a second
 * lineage (ADR-0031) deserves the undivided attention it gets in /admin/generators.
 */
export function NewGeneratorVersionDialog({
  open,
  generatorId,
  generatorName,
  onClose,
  onCreated,
}: {
  open: boolean;
  generatorId: string;
  generatorName: string;
  onClose: () => void;
  onCreated: (generatorVersionId: Uuid) => void;
}) {
  const create = useCreateGeneratorVersion();
  const [version, setVersion] = useState("");
  const [changelog, setChangelog] = useState("");

  function close() {
    setVersion("");
    setChangelog("");
    onClose();
  }

  function submit() {
    const note = changelog.trim();
    create.mutate(
      {
        generatorId,
        body: {
          version: version.trim(),
          // An empty field declares nothing — it must not write an empty key into the blob.
          ...(note ? { metadata: { [CHANGELOG_KEY]: note } } : {}),
        },
      },
      {
        onSuccess: (created) => {
          setVersion("");
          setChangelog("");
          toast.success(`${generatorName} ${created.version} registered.`);
          onCreated(created.generator_version_id);
        },
        onError: (err) => {
          const e = err as ApiError;
          toast.error(
            e.status === 409
              ? "That version is already registered."
              : "Could not register the version.",
            { description: e.message },
          );
        },
      },
    );
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={`New version of ${generatorName}`}
      description="Registers a version under this lineage. The lineage itself is never created here — a new generator is a rare, separate act."
    >
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="new-generator-version">
            Version <span className="text-destructive">*</span>
          </Label>
          <Input
            id="new-generator-version"
            value={version}
            placeholder="2.1.0"
            required
            onChange={(event) => setVersion(event.target.value)}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="new-generator-changelog">Changelog</Label>
          <Textarea
            id="new-generator-changelog"
            value={changelog}
            placeholder="What changed in this version, in a sentence or two."
            onChange={(event) => setChangelog(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Optional reference for whoever reads the results. It cannot be edited afterwards —
            the declared identity is immutable.
          </p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={close} disabled={create.isPending}>
            Cancel
          </Button>
          <Button type="submit" disabled={!version.trim() || create.isPending}>
            {create.isPending ? <Spinner /> : null} Register version
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
