"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { Batch } from "@/components/admin/batch-summary";
import {
  declaredGeneratorVersionId,
  isGeneratorDeclared,
} from "@/components/admin/generator-version-picker";
import type { ApiError } from "@/lib/api/client";
import {
  useGenerators,
  useLocalSourceFolder,
  useLocalSourceRoots,
  usePackageFormats,
  useRegisterLocalPackage,
  useScanLocalSource,
} from "@/lib/api/hooks";
import { declarationSignal, looksLikeSameGeneratorName } from "@/lib/generator-declaration";
import type { EditProvenance, ScanResponse, ScanVerdict, Uuid } from "@/lib/api/types";

/** The two the operator came to register. Everything else starts unchecked because acting
 *  on it either does nothing or is refused. */
export const REGISTRABLE: ScanVerdict[] = ["new", "new_version"];

export type Outcome = {
  status: "created" | "unchanged" | "failed" | "attributed";
  detail: string;
};

/**
 * Importing a batch of courses from a folder on the machine running the API: what is being
 * declared about them, where to look, what the scan said, and what registering did to each.
 *
 * Every screen that imports from disk runs on this, so the rules (a scan is only true for
 * what it was computed against, a declaration is never defaulted, ADR-0024 and ADR-0027 §5)
 * live in one place. Local only: the endpoints exist only under a local setup (ADR-0035).
 */
export function useImportBatch() {
  const formats = usePackageFormats();
  const roots = useLocalSourceRoots(true);
  const scanFolder = useScanLocalSource();
  const registerOne = useRegisterLocalPackage();
  const generators = useGenerators();

  // 1 · what is being declared about everything the scan finds
  const [format, setFormat] = useState("");
  const [generator, setGenerator] = useState("");
  const [version, setVersion] = useState("1");
  const [editProvenance, setEditProvenance] = useState<EditProvenance>("unknown");
  /** Registering the lineage's declared-but-unregistered version, prefilled from a scan
   *  candidate (ADR-0027 §5) — a shortcut into the same dialog `GeneratorVersionPicker`
   *  offers, never a second way to mint one. */
  const [assistedRegister, setAssistedRegister] = useState<{
    generatorId: string;
    generatorName: string;
    version: string;
  } | null>(null);

  // 2 · where to look
  const [root, setRoot] = useState("");
  const [path, setPath] = useState("");

  // 3 · what the preview said, and what registering then did to each row
  const [scan, setScan] = useState<{ result: ScanResponse; folder: string } | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  /** What the last batch touched. Held so the summary can say whether the lot came back
   *  readable, and so the round below can remount over what just arrived. */
  const [batch, setBatch] = useState<Batch | null>(null);
  /** Bumped when a batch ends, to rebuild the round below over what just arrived. */
  const [batchStamp, setBatchStamp] = useState(0);

  const folder = useLocalSourceFolder(root, path, Boolean(root));

  // A single supported format needs no choice.
  useEffect(() => {
    if (!format && formats.data?.length === 1) setFormat(formats.data[0]);
  }, [format, formats.data]);
  useEffect(() => {
    if (!root && roots.data?.length) setRoot(roots.data[0].key);
  }, [root, roots.data]);

  const generatorDeclared = isGeneratorDeclared(generator);
  const declaredGenerator: Uuid | null = generatorDeclared
    ? declaredGeneratorVersionId(generator)
    : null;

  /** What the scanned packages themselves declare, before anything is chosen above — a
   *  shortcut, never a default: nothing here is selected until the operator clicks it
   *  (ADR-0024). Only offered while nothing has been declared yet, so it never second-guesses
   *  a choice already made. */
  const declaredSuggestion = useMemo(() => {
    if (generatorDeclared) return null;
    const withDeclared = (scan?.result.candidates ?? []).find(
      (candidate) => candidate.declared_generator_name && candidate.declared_generator_version,
    );
    if (!withDeclared?.declared_generator_name || !withDeclared.declared_generator_version) {
      return null;
    }
    const lineage = (generators.data ?? []).find((g) =>
      looksLikeSameGeneratorName(g.name, withDeclared.declared_generator_name!),
    );
    return {
      name: withDeclared.declared_generator_name,
      version: withDeclared.declared_generator_version,
      resolvedId: withDeclared.resolved_generator_version_id,
      lineageId: lineage?.generator_id ?? null,
    };
  }, [scan, generatorDeclared, generators.data]);

  // A row checked before the declaration changed can end up disagreeing with it; drop it
  // rather than let a stale checkbox reach `register` and 409 (ADR-0027 §5) — the scan itself
  // stays valid (it never depended on the declaration), only the selection is pruned.
  useEffect(() => {
    setSelected((previous) =>
      previous.filter((path) => {
        const candidate = scan?.result.candidates.find((c) => c.path === path);
        return (
          !candidate ||
          declarationSignal(candidate, declaredGenerator, generatorDeclared) !== "conflict"
        );
      }),
    );
  }, [scan, declaredGenerator, generatorDeclared]);

  /** The verdicts are only true for the format, version and folder they were computed
   *  against. Rather than show labels that quietly stopped applying, drop them. */
  function invalidateScan() {
    setScan(null);
    setSelected([]);
    setOutcomes({});
    setProgress(null);
  }

  function goTo(next: string) {
    setPath(next);
    invalidateScan();
  }

  function runScan() {
    scanFolder.mutate(
      { root, path, package_format: format, version },
      {
        onSuccess: (result) => {
          setScan({ result, folder: `${root}${path ? `/${path}` : ""}` });
          setOutcomes({});
          setProgress(null);
          setSelected(
            result.candidates
              .filter(
                (candidate) =>
                  REGISTRABLE.includes(candidate.verdict) &&
                  declarationSignal(candidate, declaredGenerator, generatorDeclared) !==
                    "conflict",
              )
              .map((candidate) => candidate.path),
          );
        },
        onError: (err) => {
          const e = err as ApiError;
          toast.error("Could not scan this folder.", { description: e.message });
        },
      },
    );
  }

  /** Registers the rows ticked, or `only` these paths when a caller decides them itself
   *  at the moment of the click (the guided flow has no checkboxes). */
  async function registerSelected(only?: string[]) {
    const paths = only ?? selected;
    const chosen = (scan?.result.candidates ?? []).filter((candidate) =>
      paths.includes(candidate.path),
    );
    setProgress({ done: 0, total: chosen.length });
    let created = 0;
    let unchanged = 0;
    let failed = 0;
    const registered: Uuid[] = [];

    // Sequential on purpose: each created course is profiled inside its own request, so
    // firing them together would hide which one is slow and multiply the load for nothing.
    for (const candidate of chosen) {
      try {
        const result = await registerOne.mutateAsync({
          root,
          path: candidate.path,
          package_format: format,
          version,
          generator_version_id: declaredGenerator,
          edit_provenance: editProvenance,
        });
        created += result.created ? 1 : 0;
        unchanged += result.created ? 0 : 1;
        // Every course the batch touched, created or not: the summary below answers "was
        // this lot read", and an already-registered course is as much part of the lot.
        registered.push(result.content.content_id);
        setOutcomes((previous) => ({
          ...previous,
          [candidate.path]: {
            status: result.created ? "created" : "unchanged",
            detail: result.created
              ? `${result.artifact_count} artifacts`
              : "the same bytes were already registered",
          },
        }));
      } catch (err) {
        failed += 1;
        const e = err as ApiError;
        setOutcomes((previous) => ({
          ...previous,
          [candidate.path]: { status: "failed", detail: e.message },
        }));
      }
      setProgress((previous) => (previous ? { ...previous, done: previous.done + 1 } : previous));
    }

    setProgress(null);
    setSelected([]);
    setBatch({ contentIds: registered, created, unchanged, failed });
    setBatchStamp((previous) => previous + 1);
    const summary = `${created} registered, ${unchanged} unchanged, ${failed} failed`;
    if (failed) toast.error("Some courses could not be registered.", { description: summary });
    else toast.success("Import finished.", { description: summary });
  }

  return {
    formats,
    roots,
    scanFolder,
    folder,
    format,
    setFormat,
    version,
    setVersion,
    generator,
    setGenerator,
    editProvenance,
    setEditProvenance,
    assistedRegister,
    setAssistedRegister,
    root,
    setRoot,
    path,
    setPath,
    scan,
    selected,
    setSelected,
    outcomes,
    setOutcomes,
    progress,
    batch,
    batchStamp,
    generatorDeclared,
    declaredGenerator,
    declaredSuggestion,
    invalidateScan,
    goTo,
    runScan,
    registerSelected,
  };
}
