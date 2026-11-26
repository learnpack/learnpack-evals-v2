"use client";

import Link from "next/link";
import { Folder, RefreshCw } from "lucide-react";
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
import { BatchSummary } from "@/components/admin/batch-summary";
import { FolderBreadcrumb } from "@/components/admin/folder-breadcrumb";
import { NewGeneratorVersionDialog } from "@/components/admin/generator-version-dialog";
import { GeneratorVersionPicker } from "@/components/admin/generator-version-picker";
import { StudyForm } from "@/components/admin/study-form";
import type { ApiError } from "@/lib/api/client";
import { useAttributeGenerator, useContents, useGeneratorVersions } from "@/lib/api/hooks";
import { REGISTRABLE, useImportBatch, type Outcome } from "@/lib/use-import-batch";
import { groupByVersion } from "@/lib/versions";
import { declarationSignal } from "@/lib/generator-declaration";
import type { EditProvenance, ScanCandidate, ScanVerdict, Uuid } from "@/lib/api/types";
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


export default function ImportCoursesPage() {
  // A build-time constant, so the whole page drops out of a production bundle. Reaching it
  // there anyway would only find 404s: the endpoints do not exist outside local mode.
  if (!IS_LOCAL_AUTH) {
    return (
      <div className="max-w-3xl">
        <EmptyState
          title="Importing from disk is a local development affordance"
          hint="It reads folders on the machine running the API, so it exists only on a local setup. In a deployed console the same errand is two screens: Courses → Add course, then Studies → New study."
        />
      </div>
    );
  }
  return <ImportFromDisk />;
}

function ImportFromDisk() {
  const {
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
    adoptNewGeneratorVersion,
    registerSelected,
  } = useImportBatch();

  if (roots.isLoading || formats.isLoading) return <LoadingState />;
  const loadError = roots.error ?? formats.error;
  if (loadError) return <ErrorState message={(loadError as Error).message} />;

  const registrable = selected.length;
  const mountBroken = scan?.result.mount_ok === false;
  const canRegister = Boolean(scan) && !mountBroken && generatorDeclared && registrable > 0;

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Import &amp; measure</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          One errand, top to bottom: say which generator version made these courses, bring
          them in from a folder on the machine running the API, and start the study that
          measures them. Every folder inside the one you scan is one course. Nothing is fixed
          until you start the study. It works only on a local setup.
        </p>
        <p className="mt-2 text-sm">
          This is the view with every option.{" "}
          <Link href="/admin/measure" className="text-primary hover:underline">
            The guided flow
          </Link>{" "}
          asks the same in three steps.
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

          {declaredSuggestion ? (
            <div className="sm:col-span-2 rounded-md border border-primary/30 bg-primary/5 p-3 text-sm">
              <p>
                The scanned packages declare{" "}
                <strong>
                  {declaredSuggestion.name} {declaredSuggestion.version}
                </strong>
                .
              </p>
              {declaredSuggestion.resolvedId ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => setGenerator(declaredSuggestion.resolvedId!)}
                >
                  Use this version
                </Button>
              ) : declaredSuggestion.lineageId ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() =>
                    setAssistedRegister({
                      generatorId: declaredSuggestion.lineageId!,
                      generatorName: declaredSuggestion.name,
                      version: declaredSuggestion.version,
                    })
                  }
                >
                  Register {declaredSuggestion.name} {declaredSuggestion.version} now
                </Button>
              ) : (
                <p className="mt-2 text-xs text-muted-foreground">
                  No lineage named &quot;{declaredSuggestion.name}&quot; is registered —{" "}
                  <Link href="/admin/generators" className="text-primary hover:underline">
                    register it
                  </Link>{" "}
                  first.
                </p>
              )}
            </div>
          ) : null}

          <NewGeneratorVersionDialog
            open={assistedRegister !== null}
            generatorId={assistedRegister?.generatorId ?? ""}
            generatorName={assistedRegister?.generatorName ?? ""}
            initialVersion={assistedRegister?.version ?? ""}
            onClose={() => setAssistedRegister(null)}
            onCreated={adoptNewGeneratorVersion}
          />

          <div className="space-y-1.5">
            <Label htmlFor="import-provenance">Was it edited by a person?</Label>
            <Select
              id="import-provenance"
              value={editProvenance}
              onChange={(event) => setEditProvenance(event.target.value as EditProvenance)}
            >
              <option value="unknown">Don&apos;t know</option>
              <option value="pure">No, pure generator output</option>
              <option value="human_edited">Yes</option>
            </Select>
            <p className="text-xs text-muted-foreground">
              A lot somebody went over by hand and a lot straight out of the generator are
              different populations — and the generator only answers for one of them.
            </p>
          </div>
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

          <FolderBreadcrumb root={root} path={path} onNavigate={goTo} />

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
                    generatorDeclared={generatorDeclared}
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
                    <Button onClick={() => registerSelected()} disabled={!canRegister || progress !== null}>
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

                  <BatchSummary batch={batch} format={format} />
                </>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* 3 --------------------------------------------------------------------- measure
          No Card of its own: `StudyForm` is one already, and a card inside a card would
          draw a box around a box for nothing. */}
      <div className="space-y-3">
        <div className="text-lg font-semibold leading-none tracking-tight">3 · Measure</div>
        <ComposeRound
          generatorVersionId={declaredGenerator}
          generatorDeclared={generatorDeclared}
          batchStamp={batchStamp}
        />
      </div>
    </div>
  );
}

/**
 * The round, composed where the courses arrived.
 *
 * This is `StudyForm` and nothing else — the same instrument, judge, scope and commissions
 * it asks for anywhere, prefilled with what the page above already declared. Composing a
 * dataset in a second place would be a second set of rules to keep in step.
 *
 * The remount is the delicate part. The form reads its initial values once, at mount, so it
 * has to be rebuilt when the declared version changes and when a batch finishes — otherwise
 * the courses just imported would not be ticked, which is the whole errand. The cost is that
 * a batch discards anything already typed below. Accepted because the page reads top to
 * bottom: you import, and *then* you scroll down to compose.
 */
function ComposeRound({
  generatorVersionId,
  generatorDeclared,
  batchStamp,
}: {
  generatorVersionId: Uuid | null;
  generatorDeclared: boolean;
  batchStamp: number;
}) {
  const contents = useContents();
  const generatorVersions = useGeneratorVersions();

  if (!generatorDeclared || generatorVersionId === null) {
    return (
      <p className="rounded border bg-muted/40 p-3 text-sm text-muted-foreground">
        {generatorDeclared
          ? "These courses declare no generator, and a study names the versions it measures — so there is nothing here to compose. Attribute one from Courses to bring them in."
          : "Declare above which generator version made these courses. A study measures versions, so it cannot be composed until one is named."}
      </p>
    );
  }

  // Mounting before the courses arrive would freeze the commissions at none, and the form
  // would never pick them up — it reads them once.
  if (contents.data === undefined || generatorVersions.data === undefined) {
    return <LoadingState label="Reading what this version made…" />;
  }

  const group = groupByVersion(contents.data, generatorVersions.data).find(
    (candidate) => candidate.key === generatorVersionId,
  );
  const version = generatorVersions.data.find(
    (candidate) => candidate.generator_version_id === generatorVersionId,
  );

  if (!group || group.briefIds.size === 0) {
    return (
      <p className="rounded border bg-muted/40 p-3 text-sm text-muted-foreground">
        Nothing is registered against {version ? `${version.name} ${version.version}` : "this version"}{" "}
        yet. Register the courses above and the study will compose itself from what they
        brought.
      </p>
    );
  }

  return (
    <StudyForm
      key={`${generatorVersionId}:${batchStamp}`}
      // Here the form is the last stretch of a page, not the page: taking focus would
      // scroll the reader past the folder they had not chosen yet, and again after every
      // batch.
      autoFocusName={false}
      initialName={version ? `${version.name} ${version.version}` : undefined}
      initialScope={[generatorVersionId]}
      initialBriefIds={[...group.briefIds]}
    />
  );
}

function CandidateTable({
  candidates,
  selected,
  outcomes,
  busy,
  onToggle,
  declaredGenerator,
  generatorDeclared,
  onAttributed,
}: {
  candidates: ScanCandidate[];
  selected: string[];
  outcomes: Record<string, Outcome>;
  busy: boolean;
  onToggle: (path: string) => void;
  declaredGenerator: Uuid | null;
  generatorDeclared: boolean;
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
          const signal = declarationSignal(candidate, declaredGenerator, generatorDeclared);
          const registrable =
            REGISTRABLE.includes(candidate.verdict) && !outcome && signal !== "conflict";
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
                {/* The scan has read the package's own name all along (ADR-0059); the id
                    below it is what the registration will key on. */}
                {candidate.title ? (
                  <span className="block font-medium">{candidate.title}</span>
                ) : null}
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
                    generatorDeclared={generatorDeclared}
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
  generatorDeclared,
  busy,
  onAttributed,
}: {
  candidate: ScanCandidate;
  declaredGenerator: Uuid | null;
  generatorDeclared: boolean;
  busy: boolean;
  onAttributed: () => void;
}) {
  const attribute = useAttributeGenerator();
  const signal = declarationSignal(candidate, declaredGenerator, generatorDeclared);

  // Takes priority over every verdict-specific note below: it says why the row cannot be
  // registered as declared, which is the more actionable fact regardless of what else the
  // verdict says (ADR-0027 §5 — refused outright, no override).
  if (signal === "conflict") {
    return (
      <span className="text-destructive">
        this package declares{" "}
        <strong>
          {candidate.declared_generator_name} {candidate.declared_generator_version}
        </strong>
        , not what you declared above — fix the declaration or exclude this folder
      </span>
    );
  }

  const notice =
    signal === "notice" ? (
      <span className="block text-amber-700 dark:text-amber-400">
        this package declares {candidate.declared_generator_name}{" "}
        {candidate.declared_generator_version}; registering as unknown
      </span>
    ) : null;

  if (candidate.verdict === "unreadable") {
    return (
      <span className="line-clamp-2" title={candidate.error ?? undefined}>
        {candidate.error}
      </span>
    );
  }

  if (candidate.verdict === "conflict") {
    return (
      <>
        {notice}
        <span>
          version {candidate.existing?.version} already registered with different bytes — bump
          the course version above to register these as a new version
        </span>
      </>
    );
  }

  if (candidate.verdict === "new_version") {
    return (
      <>
        {notice}
        <span>already registered as version {candidate.existing?.version}, with other bytes</span>
      </>
    );
  }

  if (candidate.verdict === "unchanged") {
    return (
      <>
        {notice}
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
                      toast.error("Could not attribute.", {
                        description: (err as ApiError).message,
                      }),
                  },
                )
              }
            >
              {attribute.isPending ? <Spinner /> : null} Attribute generator
            </Button>
          ) : null}
          {candidate.can_attribute_generator && !declaredGenerator ? (
            <span className="text-amber-700 dark:text-amber-400">its generator is unknown</span>
          ) : null}
        </span>
      </>
    );
  }

  return (
    <>
      {notice}
      <span className={cn(!candidate.title && "italic")}>{candidate.title ?? "no title"}</span>
    </>
  );
}
