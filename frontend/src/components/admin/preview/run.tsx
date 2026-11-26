"use client";

import { Spinner } from "@/components/ui/states";
import { ReadPackagesButton } from "@/components/admin/read-packages-button";
import type {
  PreviewOutcome,
  PreviewRun,
  PreviewRunError,
  PreviewRunStep,
  Uuid,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

/* The pieces of a dry run every screen that runs one shows: its progress, why it failed, and
 * the evidence behind one outcome. Calibration and Try one course both read a run through
 * them, so a run looks the same wherever it is read. */

function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

/** What the run is doing, while it does it.
 *
 * One line per executed criterion and per LLM attempt — which is where the minutes
 * actually go. The elapsed time comes from the server, so the page never has to
 * reconcile two clocks. */
export function RunProgress({ run }: { run: PreviewRun }) {
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
export function RunFailure({
  error,
  contentId,
  calibration = false,
}: {
  error: PreviewRunError;
  contentId: Uuid | "";
  /** On Calibration, which runs drafts and shows the model calls below the run. The advice
   *  for two of the failures depends on both. */
  calibration?: boolean;
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
          {calibration
            ? "Re-import the YAML and pick the version again — this page runs drafts on purpose."
            : "Choose the instrument again: the list offers the versions published now."}
        </p>
      ) : null}
      {error.kind === "assessor_failed" ? (
        <p className="text-xs text-muted-foreground">
          Nothing was saved, so running it again is the retry.
          {calibration
            ? " If it keeps happening, the trace below has the prompt each task sent and the raw text it got back."
            : " If it keeps happening, Calibration runs the same thing and shows every model call."}
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

export function OutcomeEvidence({ outcome }: { outcome: PreviewOutcome }) {
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
