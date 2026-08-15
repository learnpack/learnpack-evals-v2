"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Folder, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  GeneratorVersionPicker,
  declaredGeneratorVersionId,
  isGeneratorDeclared,
} from "@/components/admin/generator-version-picker";
import type { ApiError } from "@/lib/api/client";
import {
  useAttributeGenerator,
  useLocalSourceFolder,
  useLocalSourceRoots,
  usePackageFormats,
  useRegisterLocalPackage,
  useScanLocalSource,
} from "@/lib/api/hooks";
import type { ScanCandidate, ScanResponse, ScanVerdict, Uuid } from "@/lib/api/types";
import { IS_LOCAL_AUTH } from "@/lib/auth";
import { cn } from "@/lib/utils";

const VERDICT_VARIANT: Record<ScanVerdict, BadgeProps["variant"]> = {
  new: "success",
  new_version: "default",
  unchanged: "secondary",
  conflict: "warning",
  unreadable: "outline",
};

const VERDICT_LABEL: Record<ScanVerdict, string> = {
  new: "new",
  new_version: "new version",
  unchanged: "already registered",
  conflict: "conflict",
  unreadable: "not a course",
};

/** The two the operator came to register. Everything else starts unchecked because acting
 *  on it either does nothing or is refused. */
const REGISTRABLE: ScanVerdict[] = ["new", "new_version"];

type Outcome = { status: "created" | "unchanged" | "failed" | "attributed"; detail: string };

export default function ImportCoursesPage() {
  // A build-time constant, so the whole page drops out of a production bundle. Reaching it
  // there anyway would only find 404s: the endpoints do not exist outside local mode.
  if (!IS_LOCAL_AUTH) {
    return (
      <div className="max-w-3xl">
        <EmptyState
          title="Importing from disk is a local development affordance"
          hint="It reads folders on the machine running the API, so it exists only under AUTH_MODE=local. Register a deployed course from Courses → Add course instead."
        />
      </div>
    );
  }
  return <ImportFromDisk />;
}

function ImportFromDisk() {
  const formats = usePackageFormats();
  const roots = useLocalSourceRoots(true);
  const scanFolder = useScanLocalSource();
  const registerOne = useRegisterLocalPackage();

  // 1 · what is being declared about everything the scan finds
  const [format, setFormat] = useState("");
  const [generator, setGenerator] = useState("");
  const [version, setVersion] = useState("1");

  // 2 · where to look
  const [root, setRoot] = useState("");
  const [path, setPath] = useState("");

  // 3 · what the preview said, and what registering then did to each row
  const [scan, setScan] = useState<{ result: ScanResponse; folder: string } | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);

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
              .filter((candidate) => REGISTRABLE.includes(candidate.verdict))
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

  async function registerSelected() {
    const chosen = (scan?.result.candidates ?? []).filter((candidate) =>
      selected.includes(candidate.path),
    );
    setProgress({ done: 0, total: chosen.length });
    let created = 0;
    let unchanged = 0;
    let failed = 0;

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
        });
        created += result.created ? 1 : 0;
        unchanged += result.created ? 0 : 1;
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
    const summary = `${created} registered, ${unchanged} unchanged, ${failed} failed`;
    if (failed) toast.error("Some courses could not be registered.", { description: summary });
    else toast.success("Import finished.", { description: summary });
  }

  if (roots.isLoading || formats.isLoading) return <LoadingState />;
  const loadError = roots.error ?? formats.error;
  if (loadError) return <ErrorState message={(loadError as Error).message} />;

  const registrable = selected.length;
  const mountBroken = scan?.result.mount_ok === false;
  const canRegister = Boolean(scan) && !mountBroken && generatorDeclared && registrable > 0;

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Import courses from disk</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Register generated courses from a folder on the machine running the API. Every folder
          inside the one you scan is treated as one course, in the format and by the generator
          declared below. Local development only.
        </p>
      </div>

      {/* 1 --------------------------------------------------------------- declaration */}
      <Card>
        <CardHeader>
          <CardTitle>1 · Declare what you are importing</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="import-format">Package format</Label>
            <Select
              id="import-format"
              value={format}
              onChange={(event) => {
                setFormat(event.target.value);
                invalidateScan();
              }}
            >
              <option value="">Choose…</option>
              {(formats.data ?? []).map((supported) => (
                <option key={supported} value={supported}>
                  {supported}
                </option>
              ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="import-version">Course version</Label>
            <Input
              id="import-version"
              value={version}
              onChange={(event) => {
                setVersion(event.target.value);
                invalidateScan();
              }}
            />
            <p className="text-xs text-muted-foreground">
              Declared, never inferred. Bump it to register changed bytes of a course already
              registered at this version.
            </p>
          </div>

          {/* Declared here, not read from a folder name: that convention belongs to the CLI
              and to `courses/` (ADR-0035 §8). Changing it does not invalidate the scan —
              the generator is no part of the package's identity or its hash. */}
          <GeneratorVersionPicker
            className="sm:col-span-2"
            value={generator}
            onChange={setGenerator}
          />
        </CardContent>
      </Card>

      {/* 2 -------------------------------------------------------------------- folder */}
      <Card>
        <CardHeader>
          <CardTitle>2 · Choose the folder that holds the courses</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {(roots.data ?? []).length > 1 ? (
            <div className="max-w-xs space-y-1.5">
              <Label htmlFor="import-root">Source root</Label>
              <Select
                id="import-root"
                value={root}
                onChange={(event) => {
                  setRoot(event.target.value);
                  setPath("");
                  invalidateScan();
                }}
              >
                {(roots.data ?? []).map((source) => (
                  <option key={source.key} value={source.key} disabled={!source.exists}>
                    {source.key}
                    {source.exists ? "" : " — missing on disk"}
                  </option>
                ))}
              </Select>
            </div>
          ) : null}

          <Breadcrumb root={root} path={path} onNavigate={goTo} />

          {folder.isLoading ? (
            <LoadingState label="Reading the folder…" />
          ) : folder.error ? (
            <ErrorState message={(folder.error as Error).message} />
          ) : (folder.data?.entries.length ?? 0) === 0 ? (
            <p className="rounded-md border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
              No folders here. If the courses are directly inside, scan this folder.
            </p>
          ) : (
            <ul className="grid gap-1 sm:grid-cols-2">
              {(folder.data?.entries ?? []).map((entry) => (
                <li key={entry.path}>
                  <button
                    type="button"
                    onClick={() => goTo(entry.path)}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-accent"
                  >
                    <Folder className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="truncate">{entry.name}</span>
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                      {entry.child_dir_count} {entry.child_dir_count === 1 ? "folder" : "folders"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center gap-3">
            <Button onClick={runScan} disabled={!format || !root || scanFolder.isPending}>
              {scanFolder.isPending ? <Spinner className="mr-2" /> : null}
              {scanFolder.isPending ? "Reading every package…" : "Scan this folder"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Reads and hashes each package to say what registering would do. Nothing is
              written.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 3 ------------------------------------------------------------------- results */}
      <Card>
        <CardHeader>
          <CardTitle>3 · Review and register</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!scan ? (
            <EmptyState
              title="Nothing scanned yet"
              hint="Pick a format and a folder above, then scan it."
            />
          ) : (
            <>
              {mountBroken ? (
                <ErrorState
                  message={
                    scan.result.mount_detail ??
                    "The API does not serve this tree, so the file links these courses would register cannot be fetched."
                  }
                />
              ) : null}

              {scan.result.candidates.length === 0 ? (
                <EmptyState
                  title="No folders inside this one"
                  hint="Every course lives in its own folder — navigate to the folder that holds them."
                />
              ) : (
                <>
                  <CandidateTable
                    candidates={scan.result.candidates}
                    selected={selected}
                    outcomes={outcomes}
                    busy={progress !== null}
                    onToggle={(candidatePath) =>
                      setSelected((previous) =>
                        previous.includes(candidatePath)
                          ? previous.filter((item) => item !== candidatePath)
                          : [...previous, candidatePath],
                      )
                    }
                    declaredGenerator={declaredGenerator}
                    onAttributed={(candidatePath) =>
                      setOutcomes((previous) => ({
                        ...previous,
                        [candidatePath]: {
                          status: "attributed",
                          detail: "generator attributed",
                        },
                      }))
                    }
                  />

                  <div className="flex flex-wrap items-center gap-3">
                    <Button onClick={registerSelected} disabled={!canRegister || progress !== null}>
                      {progress ? <Spinner className="mr-2" /> : null}
                      {progress
                        ? `Registering ${progress.done + 1} of ${progress.total}…`
                        : `Register ${registrable} ${registrable === 1 ? "course" : "courses"}`}
                    </Button>
                    <Button variant="outline" onClick={runScan} disabled={scanFolder.isPending}>
                      <RefreshCw className="h-4 w-4" /> Scan again
                    </Button>
                    {!generatorDeclared ? (
                      <p className="text-xs text-muted-foreground">
                        Declare a generator above — or <em>unknown</em> — before registering.
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Registering also profiles each new course, so it takes a while per
                        course.
                      </p>
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Breadcrumb({
  root,
  path,
  onNavigate,
}: {
  root: string;
  path: string;
  onNavigate: (path: string) => void;
}) {
  const segments = path ? path.split("/") : [];
  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <button
        type="button"
        onClick={() => onNavigate("")}
        className="rounded px-1.5 py-0.5 font-medium hover:bg-accent"
      >
        {root}
      </button>
      {segments.map((segment, index) => (
        <span key={segment + index} className="flex items-center gap-1">
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          <button
            type="button"
            onClick={() => onNavigate(segments.slice(0, index + 1).join("/"))}
            className="rounded px-1.5 py-0.5 hover:bg-accent"
          >
            {segment}
          </button>
        </span>
      ))}
    </div>
  );
}

function CandidateTable({
  candidates,
  selected,
  outcomes,
  busy,
  onToggle,
  declaredGenerator,
  onAttributed,
}: {
  candidates: ScanCandidate[];
  selected: string[];
  outcomes: Record<string, Outcome>;
  busy: boolean;
  onToggle: (path: string) => void;
  declaredGenerator: Uuid | null;
  onAttributed: (path: string) => void;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10"> </TableHead>
          <TableHead>Folder</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Course</TableHead>
          <TableHead>What it means</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {candidates.map((candidate) => {
          const outcome = outcomes[candidate.path];
          const registrable = REGISTRABLE.includes(candidate.verdict) && !outcome;
          return (
            <TableRow key={candidate.path}>
              <TableCell>
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  checked={selected.includes(candidate.path)}
                  disabled={!registrable || busy}
                  onChange={() => onToggle(candidate.path)}
                  aria-label={`Register ${candidate.name}`}
                />
              </TableCell>
              <TableCell className="font-medium">{candidate.name}</TableCell>
              <TableCell>
                {outcome ? (
                  <Badge variant={outcome.status === "failed" ? "destructive" : "success"}>
                    {outcome.status}
                  </Badge>
                ) : (
                  <Badge variant={VERDICT_VARIANT[candidate.verdict]}>
                    {VERDICT_LABEL[candidate.verdict]}
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-xs">
                {candidate.external_id ?? "—"}
                {candidate.artifact_count ? (
                  <span className="ml-1 text-muted-foreground">
                    ({candidate.artifact_count} artifacts)
                  </span>
                ) : null}
              </TableCell>
              <TableCell className="max-w-sm text-xs text-muted-foreground">
                {outcome ? (
                  outcome.detail
                ) : (
                  <CandidateNote
                    candidate={candidate}
                    declaredGenerator={declaredGenerator}
                    busy={busy}
                    onAttributed={() => onAttributed(candidate.path)}
                  />
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function CandidateNote({
  candidate,
  declaredGenerator,
  busy,
  onAttributed,
}: {
  candidate: ScanCandidate;
  declaredGenerator: Uuid | null;
  busy: boolean;
  onAttributed: () => void;
}) {
  const attribute = useAttributeGenerator();

  if (candidate.verdict === "unreadable") {
    return (
      <span className="line-clamp-2" title={candidate.error ?? undefined}>
        {candidate.error}
      </span>
    );
  }

  if (candidate.verdict === "conflict") {
    return (
      <span>
        version {candidate.existing?.version} already registered with different bytes — bump the
        course version above to register these as a new version
      </span>
    );
  }

  if (candidate.verdict === "new_version") {
    return <span>already registered as version {candidate.existing?.version}, with other bytes</span>;
  }

  if (candidate.verdict === "unchanged") {
    return (
      <span className="flex flex-wrap items-center gap-2">
        <span>
          identical bytes registered as version {candidate.existing?.version} —{" "}
          <Link href="/admin/contents" className="text-primary hover:underline">
            see it in Courses
          </Link>
        </span>
        {/* Re-registering cannot fill this in: the no-op returns the existing content and
            discards the generator just declared. Attribution is its own act (ADR-0024). */}
        {candidate.can_attribute_generator && declaredGenerator ? (
          <Button
            size="sm"
            variant="outline"
            disabled={busy || attribute.isPending}
            onClick={() =>
              attribute.mutate(
                {
                  contentId: candidate.existing!.content_id,
                  body: { generator_version_id: declaredGenerator },
                },
                {
                  onSuccess: () => {
                    toast.success("Generator attributed.");
                    onAttributed();
                  },
                  onError: (err) =>
                    toast.error("Could not attribute.", { description: (err as ApiError).message }),
                },
              )
            }
          >
            {attribute.isPending ? <Spinner /> : null} Attribute generator
          </Button>
        ) : null}
        {candidate.can_attribute_generator && !declaredGenerator ? (
          <span className="text-amber-700">its generator is unknown</span>
        ) : null}
      </span>
    );
  }

  return <span className={cn(!candidate.title && "italic")}>{candidate.title ?? "no title"}</span>;
}
