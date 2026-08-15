"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { NewGeneratorVersionDialog } from "@/components/admin/generator-version-dialog";
import { useGenerators, useGeneratorVersions } from "@/lib/api/hooks";
import type { Uuid } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** The declared "no generator" answer — distinct from the unchosen placeholder (ADR-0024). */
export const UNKNOWN_GENERATOR = "unknown";

/** Whether the three-state field has been answered at all. `""` is nobody having said
 *  anything, which the endpoints refuse — and which is not the same as declaring unknown. */
export function isGeneratorDeclared(value: string): boolean {
  return value === UNKNOWN_GENERATOR || Boolean(value);
}

/** The declaration as the API takes it. Only meaningful once `isGeneratorDeclared`. */
export function declaredGeneratorVersionId(value: string): Uuid | null {
  return value === UNKNOWN_GENERATOR ? null : value;
}

/**
 * Choosing which generator version made something — the two grains of ADR-0031 as two
 * selects, with the act that fills the second one in place.
 *
 * A version is what changes often in early development, so needing one that is not
 * registered yet is the ordinary case, not the exception: `New` registers it here rather
 * than sending anyone to /admin/generators mid-errand. The lineage is not creatable here on
 * purpose — see the dialog.
 *
 * The value is the three-state declaration itself, so the caller never handles two fields:
 * `""` unanswered · `"unknown"` declared absent · a version id.
 */
export function GeneratorVersionPicker({
  value,
  onChange,
  allowUnknown = true,
  required = false,
  disabled = false,
  className,
}: {
  value: string;
  onChange: (next: string) => void;
  /** Attribution cannot declare unknown — naming the version is the whole act (ADR-0024). */
  allowUnknown?: boolean;
  required?: boolean;
  disabled?: boolean;
  className?: string;
}) {
  // The lineage list comes from the lineages, not from the versions: a generator registered
  // a moment ago has none yet, and that is exactly when `New` is needed.
  const { data: generators } = useGenerators();
  const { data: versions } = useGeneratorVersions();

  const [lineage, setLineage] = useState("");
  const [creating, setCreating] = useState(false);

  const declaresUnknown = value === UNKNOWN_GENERATOR;

  const lineages = useMemo(
    () => [...(generators ?? [])].sort((a, b) => a.name.localeCompare(b.name)),
    [generators],
  );

  const versionsOfLineage = useMemo(
    () =>
      (versions ?? [])
        .filter((version) => version.generator_id === lineage)
        .sort((a, b) => a.version.localeCompare(b.version)),
    [versions, lineage],
  );

  // A value set from outside names its own lineage; adopt it so the two selects agree. Only
  // while nothing has been chosen here, so it never overrides the person using the form.
  useEffect(() => {
    if (lineage || !value || declaresUnknown) return;
    const chosen = (versions ?? []).find((version) => version.generator_version_id === value);
    if (chosen) setLineage(chosen.generator_id);
  }, [lineage, value, declaresUnknown, versions]);

  // A lineage with a single version needs no choice.
  useEffect(() => {
    if (versionsOfLineage.length !== 1) return;
    const only = versionsOfLineage[0].generator_version_id;
    if (value !== only) onChange(only);
  }, [versionsOfLineage, value, onChange]);

  function chooseLineage(next: string) {
    if (next === UNKNOWN_GENERATOR) {
      setLineage("");
      onChange(UNKNOWN_GENERATOR);
      return;
    }
    setLineage(next);
    // The version belonged to the previous lineage — keeping it would declare a version of
    // one generator as another's.
    onChange("");
  }

  const noneRegistered = lineages.length === 0;

  return (
    <div className={cn("grid gap-4 sm:grid-cols-2", className)}>
      <div className="space-y-1.5">
        <Label htmlFor="generator-lineage">
          Generator {required ? <span className="text-destructive">*</span> : null}
        </Label>
        <Select
          id="generator-lineage"
          value={declaresUnknown ? UNKNOWN_GENERATOR : lineage}
          required={required}
          disabled={disabled}
          onChange={(event) => chooseLineage(event.target.value)}
        >
          <option value="" disabled>
            Choose…
          </option>
          {allowUnknown ? (
            <option value={UNKNOWN_GENERATOR}>Unknown — cannot be attributed by name</option>
          ) : null}
          {lineages.map((generator) => (
            <option key={generator.generator_id} value={generator.generator_id}>
              {generator.name}
            </option>
          ))}
        </Select>
        {declaresUnknown ? (
          <p className="text-xs text-muted-foreground">
            Excluded from generator-level accumulation. The link can still be filled in later,
            once.
          </p>
        ) : noneRegistered ? (
          <p className="text-xs text-muted-foreground">
            No generator registered yet — register one in{" "}
            <Link href="/admin/generators" className="text-primary hover:underline">
              Generators
            </Link>
            {allowUnknown ? ", or declare unknown." : "."}
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="generator-version">
          Generator version{" "}
          {required && !declaresUnknown ? <span className="text-destructive">*</span> : null}
        </Label>
        <div className="flex gap-2">
          <Select
            id="generator-version"
            className="min-w-0"
            value={declaresUnknown ? "" : value}
            required={required && !declaresUnknown}
            disabled={disabled || !lineage || declaresUnknown}
            onChange={(event) => onChange(event.target.value)}
          >
            <option value="" disabled>
              {lineage && !declaresUnknown ? "Choose…" : "—"}
            </option>
            {versionsOfLineage.map((version) => (
              <option key={version.generator_version_id} value={version.generator_version_id}>
                {version.version}
              </option>
            ))}
          </Select>
          <Button
            type="button"
            variant="outline"
            disabled={disabled || !lineage || declaresUnknown}
            onClick={() => setCreating(true)}
          >
            New
          </Button>
        </div>
        {!declaresUnknown ? (
          <p className="text-xs text-muted-foreground">
            Not registered yet? <strong>New</strong> adds it to this lineage without leaving
            this form.
          </p>
        ) : null}
      </div>

      <NewGeneratorVersionDialog
        open={creating}
        generatorId={lineage}
        generatorName={lineages.find((g) => g.generator_id === lineage)?.name ?? ""}
        onClose={() => setCreating(false)}
        onCreated={(generatorVersionId) => {
          onChange(generatorVersionId);
          setCreating(false);
        }}
      />
    </div>
  );
}
