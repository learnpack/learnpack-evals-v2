"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
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
import {
  GeneratorVersionPicker,
  declaredGeneratorVersionId,
  isGeneratorDeclared,
} from "@/components/admin/generator-version-picker";
import { usePackageFormats, useRegisterBySource } from "@/lib/api/hooks";
import type { EditProvenance } from "@/lib/api/types";
import {
  getServerSnapshot,
  getSnapshot,
  reset,
  start,
  stop,
  subscribe,
  type ImportRow,
  type RowStatus,
} from "@/lib/course-import-run";
import { UnusableCourseList, readCourseList, type CourseList } from "@/lib/course-list";

/** Exhaustive by type: a fifth outcome does not compile until somebody gives it a colour. */
const STATUS_VARIANT: Record<RowStatus, BadgeProps["variant"]> = {
  pending: "outline",
  created: "success",
  unchanged: "secondary",
  conflict: "warning",
  invalid: "destructive",
};

/** The CLI's own four words for how a row ended, plus the one for a row not reached yet. */
const STATUS_LABEL: Record<RowStatus, string> = {
  pending: "pending",
  created: "created",
  unchanged: "unchanged",
  conflict: "conflict",
  invalid: "invalid",
};

/**
 * Registering a generation from the list of URLs somebody deployed it to.
 *
 * The act underneath is the one `Add course` performs, once per row (ADR-0027): identity,
 * artifact list and content hash are discovered from each package, and the URL the file
 * names is also the course's deployed instance, so registering this way declares the
 * deployment too (ADR-0028) — which is the errand, since a course with no consumable URL
 * can be judged automatically but never handed to a person.
 *
 * Nothing is uploaded: the file is read in the browser, and what reaches the API is one
 * ordinary registration per URL.
 */
export default function ImportCourseListPage() {
  const formats = usePackageFormats();
  const registerBySource = useRegisterBySource();
  // The run lives outside this component on purpose — see `lib/course-import-run`. The page
  // is a window on it, so leaving and coming back finds the same batch still moving.
  const run = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  // 1 · what is being declared about every course in the file
  const [format, setFormat] = useState("");
  const [version, setVersion] = useState("1");
  const [generator, setGenerator] = useState("");
  const [editProvenance, setEditProvenance] = useState<EditProvenance>("unknown");

  // 2 · what the file named, or why it named nothing usable
  const [file, setFile] = useState<{ name: string; list: CourseList } | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  // A single supported format needs no choice — preselect it, keep the select visible.
  useEffect(() => {
    if (!format && formats.data?.length === 1) setFormat(formats.data[0]);
  }, [format, formats.data]);

  // The browser's own confirm, while it is the only thing that matters: client-side
  // navigation does not stop the loop, but closing or reloading the tab does.
  useEffect(() => {
    if (!run.running) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [run.running]);

  async function chooseFile(event: React.ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0];
    // Cleared straight away, so picking the same file twice is not a silent no-op.
    event.target.value = "";
    if (!chosen) return;
    reset();
    setFile(null);
    setFileError(null);
    try {
      setFile({ name: chosen.name, list: readCourseList(await chosen.text()) });
    } catch (error) {
      setFileError(
        error instanceof UnusableCourseList ? error.message : "This file could not be read.",
      );
    }
  }

  function registerAll() {
    if (!file) return;
    void start({
      urls: file.list.urls,
      declaration: {
        package_format: format,
        version: version.trim(),
        // Three states, not two (ADR-0024): the placeholder never reaches here, and
        // "unknown" is a declaration rather than the absence of one.
        generator_version_id: declaredGeneratorVersionId(generator),
        edit_provenance: editProvenance,
      },
      register: registerBySource.mutateAsync,
      announce: (finished) => {
        const summary = `${finished.created} created, ${finished.unchanged} unchanged, ${finished.failed} failed`;
        if (finished.stopped) toast.warning("Import stopped.", { description: summary });
        else if (finished.failed) {
          toast.error("Some courses could not be registered.", { description: summary });
        } else toast.success("Import finished.", { description: summary });
      },
    });
  }

  /**
   * Everything that would fail identically for every row, refused once — before the first
   * course is fetched. It is the property the CLI documents at the other door: learning on
   * course nineteen what course one already knew costs eighteen courses' worth of reading.
   */
  const blocker = !format
    ? "Choose the package format above."
    : !version.trim()
      ? "Give these courses a version above."
      : !isGeneratorDeclared(generator)
        ? "Declare a generator above — or unknown — before registering."
        : !file
          ? "Choose a file above."
          : null;

  // Before a run, the file's URLs are the table: the operator should see exactly what is
  // about to be registered, in the order it will happen.
  const rows: ImportRow[] = useMemo(
    () =>
      run.rows.length > 0
        ? run.rows
        : (file?.list.urls ?? []).map((url) => ({ url, status: "pending", detail: "" })),
    [run.rows, file],
  );

  const batch =
    run.ended && run.contentIds.length > 0
      ? {
          contentIds: run.contentIds,
          created: run.created,
          unchanged: run.unchanged,
          failed: run.failed,
        }
      : null;

  if (formats.isLoading) return <LoadingState />;
  if (formats.error) return <ErrorState message={(formats.error as Error).message} />;

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <Link
          href="/admin/contents"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Courses
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Import from a list</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          A generation, from the list of URLs it was deployed to. Say what the file is a list
          of, choose it, and every row is registered the way <em>Add course</em> registers
          one — and because the URL is the running course, registering it also declares where
          a person can open it.
        </p>
      </div>

      {/* 1 --------------------------------------------------------------- declaration */}
      <Card>
        <CardHeader>
          <CardTitle>1 · Declare what you are registering</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="list-format">Package format</Label>
            <Select
              id="list-format"
              value={format}
              onChange={(event) => setFormat(event.target.value)}
              disabled={run.running}
            >
              <option value="">Choose…</option>
              {(formats.data ?? []).map((supported) => (
                <option key={supported} value={supported}>
                  {supported}
                </option>
              ))}
            </Select>
            <p className="text-xs text-muted-foreground">
              One format for the whole file. A list mixing two is two files.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="list-version">Course version</Label>
            <Input
              id="list-version"
              value={version}
              onChange={(event) => setVersion(event.target.value)}
              disabled={run.running}
            />
            <p className="text-xs text-muted-foreground">
              Declared, never inferred. Bump it to register changed bytes of a course already
              registered at this version.
            </p>
          </div>

          {/* One generator for the whole file, exactly as the CLI declares one for the whole
              run. A typo here would not mint one stray version, it would attribute a whole
              list to it — which is why the picker registers a version explicitly or not at
              all (ADR-0031). */}
          <GeneratorVersionPicker
            className="sm:col-span-2"
            value={generator}
            onChange={setGenerator}
            disabled={run.running}
          />

          <div className="space-y-1.5">
            <Label htmlFor="list-provenance">Was it edited by a person?</Label>
            <Select
              id="list-provenance"
              value={editProvenance}
              onChange={(event) => setEditProvenance(event.target.value as EditProvenance)}
              disabled={run.running}
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

      {/* 2 ---------------------------------------------------------------------- file */}
      <Card>
        <CardHeader>
          <CardTitle>2 · Choose the file</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={chooseFile}
            disabled={run.running}
            aria-label="Course list"
            className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border file:border-input file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-secondary-foreground hover:file:bg-accent disabled:opacity-50"
          />
          <p className="text-xs text-muted-foreground">
            The first column of each row and nothing else, so a spreadsheet with the course
            name beside the URL works as it is. A header row, blank lines, rows behind a{" "}
            <code>#</code> and repeated URLs are all skipped. Nothing is uploaded, and nothing
            is written until you register below.
          </p>

          {fileError ? <ErrorState message={fileError} /> : null}

          {file ? (
            <p className="rounded-md border bg-muted/30 p-3 text-sm tabular-nums">
              <span className="font-medium">{file.name}</span> — {file.list.urls.length}{" "}
              {file.list.urls.length === 1 ? "course URL" : "course URLs"}
              {file.list.headerSkipped ? ", header row skipped" : null}
              {file.list.duplicatesIgnored > 0
                ? `, ${file.list.duplicatesIgnored} duplicate ${
                    file.list.duplicatesIgnored === 1 ? "URL" : "URLs"
                  } ignored`
                : null}
              .
            </p>
          ) : null}
        </CardContent>
      </Card>

      {/* 3 ------------------------------------------------------------------- results */}
      <Card>
        <CardHeader>
          <CardTitle>3 · Review and register</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {rows.length === 0 ? (
            <EmptyState
              title="No file chosen yet"
              hint="Pick the list above and every course it names appears here."
            />
          ) : (
            <>
              <div className="max-h-[28rem] overflow-y-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Course URL</TableHead>
                      <TableHead className="w-32">Status</TableHead>
                      <TableHead>What it means</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((row) => (
                      <TableRow key={row.url}>
                        <TableCell className="max-w-sm truncate font-medium" title={row.url}>
                          {row.url}
                        </TableCell>
                        <TableCell>
                          <Badge variant={STATUS_VARIANT[row.status]}>
                            {STATUS_LABEL[row.status]}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-md text-xs text-muted-foreground">
                          {row.detail}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={registerAll} disabled={blocker !== null || run.running}>
                  {run.running ? <Spinner className="mr-2" /> : null}
                  {run.running
                    ? `Registering ${Math.min(run.done + 1, rows.length)} of ${rows.length}…`
                    : `Register ${rows.length} ${rows.length === 1 ? "course" : "courses"}`}
                </Button>
                {run.running ? (
                  <Button variant="outline" onClick={stop}>
                    Stop after this course
                  </Button>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  {blocker ??
                    (run.running
                      ? "You can go elsewhere in the console without stopping this; closing or reloading the tab does stop it."
                      : "Each course is fetched, read and profiled, so a long list takes a while. Running the same file again finishes whatever this run does not.")}
                </p>
              </div>

              {run.stopped ? (
                <p className="text-sm text-amber-700">
                  Stopped after {run.done} of {rows.length}. The rest were never asked for —
                  register the same file again to finish it.
                </p>
              ) : null}

              <BatchSummary batch={batch} format={run.format} />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
