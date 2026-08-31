"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { ClaimStatusBadge } from "@/components/admin/claim-status";
import { ReadPackagesButton } from "@/components/admin/read-packages-button";
import { OUTCOME_ORDER, OutcomeBadge } from "@/components/admin/outcome-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ApiError } from "@/lib/api/client";
import {
  useAssessorPackages,
  useContents,
  useInstruments,
  usePreviewRun,
  usePreviewRunTrace,
  useProfiles,
  useQualityReference,
  useStartPreviewRun,
} from "@/lib/api/hooks";
import { courseLabel } from "@/lib/courses";
import type {
  AssessorPackageResponse,
  InstrumentCriterion,
  InstrumentResponse,
  LlmCallRecord,
  PreviewEvaluationResponse,
  PreviewMetric,
  PreviewOutcome,
  PreviewRun,
  PreviewRunError,
  PreviewRunStep,
  PreviewRunTrace,
  QualityReferenceResponse,
  Uuid,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** `useSearchParams` needs a Suspense boundary or `next build` refuses to prerender the
 *  page — and CI runs only `tsc`, so this is the one thing here that no check would catch
 *  before a deploy did. */
export default function CalibrationPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <CalibrationConsole />
    </Suspense>
  );
}

function CalibrationConsole() {
  const contents = useContents();
  const profiles = useProfiles();
  const instruments = useInstruments();
  const packages = useAssessorPackages();
  const qualityReference = useQualityReference();
  const start = useStartPreviewRun();
  const params = useSearchParams();

  // Read at mount and never again. A study report links here to preselect a course and an
  // instrument; after that the selects belong to the person clicking them, and a param
  // that kept winning would fight every click.
  const [contentId, setContentId] = useState<Uuid | "">(
    () => (params.get("content") as Uuid | null) ?? "",
  );
  const [instrumentVersionId, setInstrumentVersionId] = useState(
    () => params.get("instrument") ?? "",
  );
  // The assessor is deliberately NOT preselected: the report cannot know which package
  // should run, and pre-filling a choice nobody made is how a dry run gets attributed to
  // the wrong one.
  const [assessorKey, setAssessorKey] = useState(""); // "name:version"
  const cameAbout = params.get("criterion");
  // The instrument travels with the run: the fitness projection must read the version
  // that actually ran, not whatever the select points at afterwards.
  const [started, setStarted] = useState<{
    runId: Uuid;
    instrument: InstrumentResponse;
  } | null>(null);
  const run = usePreviewRun(started?.runId ?? null);
  const trace = usePreviewRunTrace(
    started?.runId ?? null,
    run.data ? run.data.status !== "running" : false,
  );

    /** Whether a content has an `ok` profile — the dry-run's one hard prerequisite. */
  const profileStatus = useMemo(() => {
    const status = new Map<Uuid, "ok" | "failed">();
    for (const profile of profiles.data ?? []) {
      if (profile.status === "ok" || !status.has(profile.content_id)) {
        status.set(profile.content_id, profile.status);
      }
    }
    return status;
  }, [profiles.data]);

  const selectedInstrument = instruments.data?.find(
    (i) => i.instrument_version_id === instrumentVersionId,
  );

  // No hard filter by lineage: the dry-run deliberately does not compare lineages — it is
  // the only way to exercise an instrument whose lineage has no assessor yet. Matching
  // lineage just sorts first.
  const sortedPackages = useMemo(() => {
    const all = [...(packages.data ?? [])];
    const lineage = selectedInstrument?.instrument_id;
    return all.sort((a, b) => {
      const aMatch = a.instrument_id === lineage ? 0 : 1;
      const bMatch = b.instrument_id === lineage ? 0 : 1;
      return aMatch - bMatch || a.display_name.localeCompare(b.display_name);
    });
  }, [packages.data, selectedInstrument]);

  const selectedPackage = sortedPackages.find((p) => `${p.name}:${p.version}` === assessorKey);
  const running = start.isPending || run.data?.status === "running";
  const ready = contentId && instrumentVersionId && selectedPackage && !running;

  // The card carries the outcome; the toast is only for someone looking elsewhere.
  const status = run.data?.status;
  useEffect(() => {
    if (status === "done") {
      toast.success("Dry run finished.", { description: "Nothing was persisted." });
    } else if (status === "failed") {
      toast.error("The dry run failed.", { description: "The reason stays on the page." });
    }
  }, [status]);

  function runPreview() {
    if (!contentId || !instrumentVersionId || !selectedPackage || !selectedInstrument) return;
    const instrument = selectedInstrument;
    setStarted(null);
    start.mutate(
      {
        content_id: contentId,
        instrument_version_id: instrumentVersionId,
        assessor_name: selectedPackage.name,
        assessor_version: selectedPackage.version,
      },
      {
        // Only the assessor is validated before the run exists; every other way this can
        // end is the run's own error, and lands in the card below.
        onSuccess: (data) => setStarted({ runId: data.run_id, instrument }),
        onError: (err) => toast.error("The dry run could not be started.", {
          description: (err as ApiError).message,
        }),
      },
    );
  }

  if (
    contents.isLoading ||
    profiles.isLoading ||
    instruments.isLoading ||
    packages.isLoading ||
    qualityReference.isLoading
  ) {
    return <LoadingState />;
  }
  const loadError =
    contents.error ??
    profiles.error ??
    instruments.error ??
    packages.error ??
    qualityReference.error;
  if (loadError) return <ErrorState message={(loadError as Error).message} />;

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Calibration</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Run an assessor against a content&apos;s profile as a <strong>dry run</strong>: drafts
          allowed, no ratification needed, nothing persisted. Edit the instrument YAML, re-import
          it, run again — this page is the loop.
        </p>
      </div>

      <ArrivedFromReport
        preselected={Boolean(params.get("content") ?? params.get("instrument"))}
        criterion={selectedInstrument?.criteria.find((c) => c.criterion_id === cameAbout)}
        criterionId={cameAbout}
        unprofiled={Boolean(contentId) && profileStatus.get(contentId as Uuid) !== "ok"}
      />

      {/* 1 ------------------------------------------------------------------ content */}
      <Card>
        <CardHeader>
          <CardTitle>1 · Pick a content</CardTitle>
        </CardHeader>
        <CardContent>
          {contents.data && contents.data.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8" />
                    <TableHead>Course</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Format</TableHead>
                    <TableHead>Profile</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {contents.data.map((content) => {
                    const status = profileStatus.get(content.content_id);
                    const usable = status === "ok";
                    return (
                      <TableRow
                        key={content.content_id}
                        className={cn(
                          usable ? "cursor-pointer" : "cursor-not-allowed opacity-60",
                          contentId === content.content_id && "bg-muted/60",
                        )}
                        onClick={() => usable && setContentId(content.content_id)}
                      >
                        <TableCell>
                          <input
                            type="radio"
                            name="calibration-content"
                            checked={contentId === content.content_id}
                            disabled={!usable}
                            onChange={() => setContentId(content.content_id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{courseLabel(content)}</TableCell>
                        <TableCell>{content.version}</TableCell>
                        <TableCell>{content.package_format}</TableCell>
                        <TableCell>
                          {usable ? (
                            <Badge variant="success">ok</Badge>
                          ) : (
                            <div className="space-y-1">
                              <Badge variant={status === "failed" ? "destructive" : "secondary"}>
                                {status ?? "none"}
                              </Badge>
                              <ReadPackagesButton
                                label="Read it now"
                                contentIds={[content.content_id]}
                              />
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <EmptyState
              title="No contents registered"
              hint="Register a course first — the form lives on the Courses page."
            />
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            Missing a course?{" "}
            <Link href="/admin/contents" className="underline">
              Register it on the Courses page
            </Link>{" "}
            (local folders go through the CLI: <code>register-package --source &lt;dir&gt;</code>).
          </p>
        </CardContent>
      </Card>

      {/* 2 ----------------------------------------------------- instrument + assessor */}
      <Card>
        <CardHeader>
          <CardTitle>2 · Pick the instrument version and the assessor</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="calibration-instrument">Instrument version</Label>
            <Select
              id="calibration-instrument"
              value={instrumentVersionId}
              onChange={(event) => setInstrumentVersionId(event.target.value)}
            >
              <option value="">Choose…</option>
              {(instruments.data ?? []).map((instrument) => (
                <option
                  key={instrument.instrument_version_id}
                  value={instrument.instrument_version_id}
                >
                  {instrument.instrument_version_id} ({instrument.status})
                </option>
              ))}
            </Select>
            {selectedInstrument?.status === "draft" ? (
              <p className="text-xs text-muted-foreground">
                A draft runs as calibration — exactly the point. Publishing stays a separate,
                human act.
              </p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="calibration-assessor">Assessor</Label>
            <Select
              id="calibration-assessor"
              value={assessorKey}
              onChange={(event) => setAssessorKey(event.target.value)}
            >
              <option value="">Choose…</option>
              {sortedPackages.map((assessorPackage) => (
                <option
                  key={`${assessorPackage.name}:${assessorPackage.version}`}
                  value={`${assessorPackage.name}:${assessorPackage.version}`}
                >
                  {packageLabel(assessorPackage)}
                </option>
              ))}
            </Select>
            {selectedPackage?.uses_llm ? (
              <p className="text-xs text-amber-700">
                This assessor carries LLM criteria: each run spends a few real model calls and
                needs <code>LLM_API_KEY</code> configured on the backend.
              </p>
            ) : null}
            {selectedPackage && selectedInstrument &&
            selectedPackage.instrument_id !== selectedInstrument.instrument_id ? (
              <p className="text-xs text-muted-foreground">
                Different lineage than the instrument — allowed in a dry run (it is how a new
                lineage is exercised before its own assessor exists); expect{" "}
                <code>not_assessed</code> where coverage is missing.
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* 3 ---------------------------------------------------------------------- run */}
      <Card>
        <CardHeader>
          <CardTitle>3 · Run</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Button onClick={runPreview} disabled={!ready}>
              {running ? <Spinner className="mr-2" /> : null}
              {running ? "Running — LLM criteria take a while…" : "Run dry evaluation"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Nothing is persisted: no evaluation, no judgment, no events.
            </p>
          </div>

          {/* The run is read, not awaited: a lost 404 here means the backend restarted
              and forgot it — the runs live in memory, on purpose. */}
          {run.error ? <ErrorState message={(run.error as ApiError).message} /> : null}
          {run.data ? (
            <>
              <RunProgress run={run.data} />
              {run.data.error ? (
                <RunFailure error={run.data.error} contentId={contentId} />
              ) : null}
              <RunTrace trace={trace.data ?? null} />
              {run.data.result && started ? (
                <PreviewResults
                  result={run.data.result}
                  instrument={started.instrument}
                  qualityReference={qualityReference.data ?? []}
                  focusCriterionId={cameAbout}
                />
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

/** Why the reader is here, when a study report sent them.
 *
 *  Arriving with the course and the instrument already chosen is most of the value; naming
 *  what the criterion demands is the rest. The question they came with is whether the check
 *  is wrong, and reading its pass condition often answers it before anything is run. */
function ArrivedFromReport({
  preselected,
  criterion,
  criterionId,
  unprofiled,
}: {
  preselected: boolean;
  criterion: InstrumentCriterion | undefined;
  criterionId: string | null;
  unprofiled: boolean;
}) {
  if (!preselected) return null;

  return (
    <div className="space-y-1 rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm">
      <p>
        <strong>Preselected from a study report.</strong> That course failed{" "}
        {criterion ? (
          <em>{criterion.statement ?? criterion.criterion_id}</em>
        ) : criterionId ? (
          <code>{criterionId}</code>
        ) : (
          "a criterion"
        )}{" "}
        under this instrument version. Pick an assessor and run it: a dry run persists
        nothing, so this is the safe place to find out whether the criterion is wrong or the
        course is.
      </p>
      {criterion ? (
        <p className="text-xs text-muted-foreground">
          It passes when: {criterion.pass_condition}
        </p>
      ) : null}
      {unprofiled ? (
        <p className="text-xs text-muted-foreground">
          This course has no <code>ok</code> profile yet, so it cannot be dry-run until it is
          profiled — its row below carries the command.
        </p>
      ) : null}
    </div>
  );
}

function packageLabel(assessorPackage: AssessorPackageResponse): string {
  const total =
    assessorPackage.executes.length + Object.keys(assessorPackage.abstains).length;
  const llm = assessorPackage.uses_llm ? " · LLM" : "";
  return `${assessorPackage.display_name} — ${assessorPackage.instrument_id} (executes ${assessorPackage.executes.length}/${total}${llm})`;
}

// ------------------------------------------------------------------------ progress

function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

/** What the run is doing, while it does it.
 *
 * One line per executed criterion and per LLM attempt — which is where the minutes
 * actually go. The elapsed time comes from the server, so the page never has to
 * reconcile two clocks. */
function RunProgress({ run }: { run: PreviewRun }) {
  const heading =
    run.status === "running" ? "Running" : run.status === "done" ? "Finished" : "Failed";
  return (
    <div className="rounded-lg border bg-muted/20">
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2 text-sm">
        {run.status === "running" ? <Spinner /> : null}
        <span className="font-medium">{heading}</span>
        <span className="tabular-nums text-muted-foreground">{seconds(run.elapsed_ms)}</span>
        <span className="text-xs text-muted-foreground">
          · {run.steps.length} step{run.steps.length === 1 ? "" : "s"}
        </span>
      </div>
      {run.steps.length === 0 ? (
        <p className="px-4 py-3 text-xs text-muted-foreground">
          {run.status === "running"
            ? "Nothing to report yet — the first LLM task can take a while to answer."
            : "The run ended before executing anything."}
        </p>
      ) : (
        <ul className="max-h-72 space-y-0.5 overflow-y-auto px-4 py-2 font-mono text-xs">
          {run.steps.map((step, index) => (
            <StepLine key={index} step={step} />
          ))}
        </ul>
      )}
    </div>
  );
}

function StepLine({ step }: { step: PreviewRunStep }) {
  return (
    <li className={cn("flex gap-2", !step.ok && "text-destructive")}>
      <span className="shrink-0 tabular-nums text-muted-foreground">
        {(step.at_ms / 1000).toFixed(1).padStart(6)}s
      </span>
      <span className={cn("shrink-0", step.kind === "llm_call" && "text-muted-foreground")}>
        {step.label}
      </span>
      <span className="break-all text-muted-foreground">{step.detail}</span>
    </li>
  );
}

// -------------------------------------------------------------------------- failure

/** A named cause, because each one has a different remedy — and it stays on the page,
 *  unlike the toast that used to be the only thing carrying it. */
function RunFailure({
  error,
  contentId,
}: {
  error: PreviewRunError;
  contentId: Uuid | "";
}) {
  const titles: Record<PreviewRunError["kind"], string> = {
    profile_missing: "This content has no ok profile.",
    instrument_missing: "That instrument version is not there.",
    assessor_failed: "The assessor could not produce a verdict.",
    unexpected: "The run failed unexpectedly.",
  };
  return (
    <div className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm">
      <p className="font-medium text-destructive">{titles[error.kind]}</p>
      <p className="break-words text-muted-foreground">{error.message}</p>
      {error.kind === "profile_missing" && contentId ? (
        <div className="pt-1">
          <ReadPackagesButton label="Read it now" contentIds={[contentId]} />
        </div>
      ) : null}
      {error.kind === "instrument_missing" ? (
        <p className="text-xs text-muted-foreground">
          Re-import the YAML and pick the version again — this page runs drafts on purpose.
        </p>
      ) : null}
      {error.kind === "assessor_failed" ? (
        <p className="text-xs text-muted-foreground">
          Nothing was persisted (ADR-0034): the run is the retry. If it keeps happening, the
          trace below has the prompt each task sent and the raw text it got back.
        </p>
      ) : null}
      {error.kind === "unexpected" ? (
        <p className="text-xs text-muted-foreground">
          Nothing was persisted. The backend log has the traceback.
        </p>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------- trace

/** The prompts and the raw answers, which is the only place they can be read.
 *
 * One entry per ATTEMPT: a task that needed three rounds to satisfy its output contract
 * is three entries, and the second one's messages end with the validator's complaint
 * about the first — the feedback loop, legible. */
function RunTrace({ trace }: { trace: PreviewRunTrace | null }) {
  if (trace === null || trace.calls.length === 0) return null;
  const failed = trace.calls.filter((call) => call.error !== null).length;
  return (
    <CollapsibleSection
      title="LLM calls"
      badge={`${trace.calls.length} attempt${trace.calls.length === 1 ? "" : "s"}`}
      defaultOpen={false}
      meta={
        failed > 0 ? (
          <Badge variant="destructive">{failed} failed</Badge>
        ) : (
          <Badge variant="secondary">all answered</Badge>
        )
      }
      className="bg-muted/20"
    >
      <div className="space-y-2">
        {trace.calls.map((call, index) => (
          <TraceCall key={index} call={call} />
        ))}
        {trace.trace_path ? (
          <p className="pt-1 text-xs text-muted-foreground">
            Also written to <code className="rounded bg-muted px-1">{trace.trace_path}</code>{" "}
            — runs live in memory and are forgotten on restart; the file is not.
          </p>
        ) : null}
      </div>
    </CollapsibleSection>
  );
}

/** `temperature=0 · max_tokens=8000 · reasoning={"effort":"none"}` — whatever was sent. */
function describeSampling(call: LlmCallRecord): string {
  const entries = Object.entries(call.sampling ?? {});
  if (entries.length === 0) return "no sampling recorded";
  return entries
    .map(([key, value]) => `${key}=${typeof value === "object" ? JSON.stringify(value) : value}`)
    .join(" · ");
}

function TraceCall({ call }: { call: LlmCallRecord }) {
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-xs",
        call.error && "border-destructive/40 bg-destructive/5",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-medium">{call.task_id ?? "llm call"}</span>
        <span className="text-muted-foreground">attempt {call.attempt}</span>
        <span className="font-mono text-muted-foreground">
          {call.model_answered ?? call.model_requested}
        </span>
        {call.provider ? (
          // Which upstream answered: OpenRouter routes one model id to several, and they
          // do not honor `response_format` alike.
          <Badge variant="outline">{call.provider}</Badge>
        ) : null}
        {call.finish_reason && call.finish_reason !== "stop" ? (
          <Badge variant="warning">finish_reason: {call.finish_reason}</Badge>
        ) : null}
        <span className="tabular-nums text-muted-foreground">
          {call.tokens_in}→{call.tokens_out} tokens · {seconds(call.latency_ms)}
        </span>
      </div>
      {/* Always visible, never folded away: it is short, and it is the half of the
          question that a wrong answer is most often traced back to. */}
      <p className="mt-1 break-all font-mono text-muted-foreground">{describeSampling(call)}</p>
      {call.error ? <p className="mt-1 break-words text-destructive">{call.error}</p> : null}
      <div className="mt-1 flex flex-wrap gap-4">
        <details>
          <summary className="cursor-pointer text-muted-foreground">
            Prompt ({call.messages.length} message{call.messages.length === 1 ? "" : "s"})
          </summary>
          <div className="mt-1 space-y-2">
            {call.messages.map((message, index) => (
              <div key={index}>
                <p className="font-medium text-muted-foreground">{message.role}</p>
                <pre className="whitespace-pre-wrap break-words font-mono text-muted-foreground">
                  {message.content}
                </pre>
              </div>
            ))}
          </div>
        </details>
        {call.response_text !== null ? (
          <details>
            <summary className="cursor-pointer text-muted-foreground">Raw answer</summary>
            <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-muted-foreground">
              {call.response_text}
            </pre>
          </details>
        ) : null}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------- results

function PreviewResults({
  result,
  instrument,
  qualityReference,
  focusCriterionId,
}: {
  result: PreviewEvaluationResponse;
  instrument: InstrumentResponse;
  qualityReference: QualityReferenceResponse[];
  /** The criterion a study report sent the reader here about: its row is marked, so they
   *  land on the answer instead of scanning thirty of them. */
  focusCriterionId?: string | null;
}) {
  const partition = new Map<string, number>();
  for (const outcome of result.outcomes) {
    partition.set(outcome.outcome, (partition.get(outcome.outcome) ?? 0) + 1);
  }
  const llmMetrics = result.metrics.filter((m) => m.metric_id.startsWith("llm_"));
  const otherMetrics = result.metrics.filter((m) => !m.metric_id.startsWith("llm_"));

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm">
        Dry run of <strong>{result.instrument_version_id}</strong>{" "}
        <Badge variant={result.instrument_status === "published" ? "default" : "secondary"}>
          {result.instrument_status}
        </Badge>{" "}
        with <strong>{result.assessor.display_name}</strong> — nothing was persisted.
      </div>

      <div className="flex flex-wrap gap-2">
        {OUTCOME_ORDER.filter((state) => partition.has(state)).map((state) => (
          <span key={state} className="flex items-center gap-1 text-xs text-muted-foreground">
            <OutcomeBadge outcome={state} /> {partition.get(state)}
          </span>
        ))}
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Criterion</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Origin</TableHead>
              <TableHead>Evidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.outcomes.map((outcome) => (
              <TableRow
                key={outcome.criterion_id}
                className={cn(
                  outcome.criterion_id === focusCriterionId && "bg-amber-500/10",
                )}
              >
                <TableCell className="font-mono text-xs">{outcome.criterion_id}</TableCell>
                <TableCell>
                  <OutcomeBadge outcome={outcome.outcome} />
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {outcome.derived ? "derived" : "executed"}
                </TableCell>
                <TableCell className="max-w-xl text-xs">
                  <OutcomeEvidence outcome={outcome} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-medium">Claims</h3>
          <ul className="space-y-1.5">
            {result.claims.map((claim) => (
              <li key={claim.claim_id} className="flex flex-wrap items-center gap-2 text-xs">
                <ClaimStatusBadge status={claim.status} />
                <span className="font-mono">{claim.claim_id}</span>
                <span className="text-muted-foreground">
                  (
                  {Object.entries(claim.evidence_basis)
                    .filter(([, count]) => count > 0)
                    .map(([state, count]) => `${state}=${count}`)
                    .join(", ")}
                  )
                </span>
              </li>
            ))}
          </ul>
          {excludedClaims(result).length > 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Excluded (all not_applicable): {excludedClaims(result).join(", ")}
            </p>
          ) : null}
        </div>
        <div className="space-y-4">
          {llmMetrics.length > 0 ? (
            <div>
              <h3 className="mb-2 text-sm font-medium">LLM spend</h3>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {llmMetrics.map((metric) => (
                  <li key={metric.metric_id}>
                    <span className="font-mono">{metric.metric_id.slice(4)}</span>:{" "}
                    {llmSpend(metric)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {otherMetrics.length > 0 ? (
            <div>
              <h3 className="mb-2 text-sm font-medium">Metrics</h3>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {otherMetrics.map((metric) => (
                  <li key={metric.metric_id}>
                    <span className="font-mono">{metric.metric_id}</span> ={" "}
                    {JSON.stringify(metric.value)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>

      <FitnessPreview
        result={result}
        instrument={instrument}
        qualityReference={qualityReference}
      />
    </div>
  );
}

// ------------------------------------------------------------------ fitness preview

interface QualityFitnessRow {
  qualityId: string;
  dimensionId: string | null;
  fitness: number | null;
  counts: {
    pass: number;
    fail: number;
    noEvidence: number;
    excluded: number;
    executionError: number;
  };
}

interface DimensionFitnessRow {
  dimensionId: string;
  fitness: number | null;
  qualities: number;
  defined: number;
}

/** The ADR-0023 arithmetic (formula v1), locally over this one dry run.
 *
 * `pass / (pass + fail + no_evidence)`; `not_assessed`/`not_applicable`/`execution_error`
 * stay out of the denominator (ADR-0023 §2, ADR-0037 §6); an empty denominator is
 * UNDEFINED, never zero. Criteria attach to a quality through the claims that assert
 * about it, counting once per quality (set semantics). A dimension is the unweighted mean
 * of its defined qualities. */
function computeFitnessPreview(
  result: PreviewEvaluationResponse,
  instrument: InstrumentResponse,
  qualityReference: QualityReferenceResponse[],
): { qualities: QualityFitnessRow[]; dimensions: DimensionFitnessRow[] } {
  const dimensionOf = new Map(qualityReference.map((q) => [q.quality_id, q.dimension_id]));
  const outcomeOf = new Map(result.outcomes.map((o) => [o.criterion_id, o.outcome]));

  const claimsOfQuality = new Map<string, Set<string>>();
  for (const claim of instrument.claims) {
    for (const qualityId of claim.quality_ids) {
      if (!claimsOfQuality.has(qualityId)) claimsOfQuality.set(qualityId, new Set());
      claimsOfQuality.get(qualityId)!.add(claim.claim_id);
    }
  }

  const qualities: QualityFitnessRow[] = [...claimsOfQuality.entries()]
    .map(([qualityId, claimIds]) => {
      const counts = { pass: 0, fail: 0, noEvidence: 0, excluded: 0, executionError: 0 };
      for (const criterion of instrument.criteria) {
        if (!criterion.claim_ids.some((id) => claimIds.has(id))) continue;
        const outcome = outcomeOf.get(criterion.criterion_id);
        if (outcome === "pass") counts.pass += 1;
        else if (outcome === "fail") counts.fail += 1;
        else if (outcome === "no_evidence") counts.noEvidence += 1;
        else if (outcome === "execution_error") counts.executionError += 1;
        else if (outcome) counts.excluded += 1;
      }
      const denominator = counts.pass + counts.fail + counts.noEvidence;
      return {
        qualityId,
        dimensionId: dimensionOf.get(qualityId) ?? null,
        fitness: denominator === 0 ? null : counts.pass / denominator,
        counts,
      };
    })
    .sort(
      (a, b) =>
        (a.dimensionId ?? "~").localeCompare(b.dimensionId ?? "~") ||
        a.qualityId.localeCompare(b.qualityId),
    );

  const grouped = new Map<string, { scores: number[]; qualities: number }>();
  for (const row of qualities) {
    if (row.dimensionId === null) continue; // groups nowhere, rolls up nowhere
    if (!grouped.has(row.dimensionId)) grouped.set(row.dimensionId, { scores: [], qualities: 0 });
    const entry = grouped.get(row.dimensionId)!;
    entry.qualities += 1;
    if (row.fitness !== null) entry.scores.push(row.fitness);
  }
  const dimensions: DimensionFitnessRow[] = [...grouped.entries()]
    .map(([dimensionId, entry]) => ({
      dimensionId,
      fitness:
        entry.scores.length === 0
          ? null
          : entry.scores.reduce((sum, score) => sum + score, 0) / entry.scores.length,
      qualities: entry.qualities,
      defined: entry.scores.length,
    }))
    .sort((a, b) => a.dimensionId.localeCompare(b.dimensionId));

  return { qualities, dimensions };
}

/** Undefined is shown as such — a zero would say "everything measurable failed" when
 *  nothing was measurable (ADR-0023 §6). */
function FitnessValue({ value }: { value: number | null }) {
  if (value === null) return <span className="italic text-muted-foreground">undefined</span>;
  return <span className="font-medium tabular-nums">{(value * 100).toFixed(0)}%</span>;
}

function FitnessPreview({
  result,
  instrument,
  qualityReference,
}: {
  result: PreviewEvaluationResponse;
  instrument: InstrumentResponse;
  qualityReference: QualityReferenceResponse[];
}) {
  const { qualities, dimensions } = computeFitnessPreview(result, instrument, qualityReference);
  if (qualities.length === 0) return null;

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-medium">Fitness preview</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          The ADR-0023 optimization signal (formula v1: pass / (pass + fail + no_evidence)),
          computed locally over this single dry run — an orientation for calibration, not a
          verdict. The real fitness is read per study, from persisted judgments.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {dimensions.map((dimension) => (
          <span key={dimension.dimensionId} className="rounded bg-muted/60 px-2 py-1 text-xs">
            {dimension.dimensionId} <FitnessValue value={dimension.fitness} />
            <span className="ml-1 text-muted-foreground">
              ({dimension.defined}/{dimension.qualities} qualities)
            </span>
          </span>
        ))}
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Quality</TableHead>
              <TableHead>Dimension</TableHead>
              <TableHead>Fitness</TableHead>
              <TableHead>pass / fail / no_evidence</TableHead>
              <TableHead>Excluded</TableHead>
              <TableHead>Errored</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {qualities.map((row) => (
              <TableRow key={row.qualityId}>
                <TableCell className="font-mono text-xs">{row.qualityId}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {row.dimensionId ?? "—"}
                </TableCell>
                <TableCell>
                  <FitnessValue value={row.fitness} />
                </TableCell>
                <TableCell className="text-xs tabular-nums">
                  {row.counts.pass} / {row.counts.fail} / {row.counts.noEvidence}
                </TableCell>
                <TableCell className="text-xs tabular-nums text-muted-foreground">
                  {row.counts.excluded}
                </TableCell>
                <TableCell className="text-xs tabular-nums text-muted-foreground">
                  {row.counts.executionError}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        Excluded = not_assessed + not_applicable, Errored = execution_error: all outside the
        denominator on purpose — the assessor&apos;s limits, unmet format demand and this
        run&apos;s own failures are not the generator&apos;s fault (ADR-0037).
      </p>
    </div>
  );
}

function OutcomeEvidence({ outcome }: { outcome: PreviewOutcome }) {
  if (outcome.execution_cause) {
    // A malfunction, never a verdict: what failed and why, in the run's own words.
    return (
      <p className="text-violet-700 dark:text-violet-400">
        {outcome.execution_cause.task ? `${outcome.execution_cause.task} — ` : ""}
        {outcome.execution_cause.kind}: {outcome.execution_cause.message}
      </p>
    );
  }
  if (outcome.failure_mode) {
    return (
      <div className="space-y-1">
        <p className="text-destructive">{outcome.failure_mode}</p>
        {outcome.quote ? <Quote text={outcome.quote} /> : null}
      </div>
    );
  }
  if (outcome.quote) return <Quote text={outcome.quote} />;
  return <span className="text-muted-foreground">—</span>;
}

function Quote({ text }: { text: string }) {
  if (text.length <= 120) return <span className="text-muted-foreground">“{text}”</span>;
  return (
    <details>
      <summary className="cursor-pointer text-muted-foreground">
        “{text.slice(0, 120)}…”
      </summary>
      <p className="mt-1 whitespace-pre-wrap break-words text-muted-foreground">{text}</p>
    </details>
  );
}

function excludedClaims(result: PreviewEvaluationResponse): string[] {
  const excluded = result.coverage["excludedClaims"];
  return Array.isArray(excluded) ? (excluded as string[]) : [];
}

function llmSpend(metric: PreviewMetric): string {
  const value = metric.value as Record<string, unknown> | null;
  if (!value || typeof value !== "object") return JSON.stringify(metric.value);
  const model = value["model"] ?? "?";
  const calls = value["calls"] ?? "?";
  const tokensIn = value["tokens_in"] ?? "?";
  const tokensOut = value["tokens_out"] ?? "?";
  const latency = value["latency_ms"] ?? "?";
  return `${model} · ${calls} call(s) · ${tokensIn}→${tokensOut} tokens · ${latency} ms`;
}
