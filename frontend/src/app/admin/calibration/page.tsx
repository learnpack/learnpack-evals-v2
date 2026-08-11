"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import type { ApiError } from "@/lib/api/client";
import {
  useAssessorPackages,
  useContents,
  useInstruments,
  usePreviewEvaluation,
  useProfiles,
} from "@/lib/api/hooks";
import type {
  AssessorPackageResponse,
  PreviewEvaluationResponse,
  PreviewMetric,
  PreviewOutcome,
  Uuid,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

const OUTCOME_VARIANT: Record<string, BadgeProps["variant"]> = {
  pass: "success",
  fail: "destructive",
  no_evidence: "warning",
  not_applicable: "outline",
  not_assessed: "secondary",
};
const OUTCOME_ORDER = ["pass", "fail", "no_evidence", "not_applicable", "not_assessed"];

const CLAIM_VARIANT: Record<string, BadgeProps["variant"]> = {
  supported: "success",
  refuted: "destructive",
  insufficient: "warning",
};

export default function CalibrationPage() {
  const contents = useContents();
  const profiles = useProfiles();
  const instruments = useInstruments();
  const packages = useAssessorPackages();
  const preview = usePreviewEvaluation();

  const [contentId, setContentId] = useState<Uuid | "">("");
  const [instrumentVersionId, setInstrumentVersionId] = useState("");
  const [assessorKey, setAssessorKey] = useState(""); // "name:version"
  const [result, setResult] = useState<PreviewEvaluationResponse | null>(null);

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
  const ready = contentId && instrumentVersionId && selectedPackage && !preview.isPending;

  function run() {
    if (!contentId || !instrumentVersionId || !selectedPackage) return;
    preview.mutate(
      {
        content_id: contentId,
        instrument_version_id: instrumentVersionId,
        assessor_name: selectedPackage.name,
        assessor_version: selectedPackage.version,
      },
      {
        onSuccess: (data) => {
          setResult(data);
          toast.success("Dry run finished.", { description: "Nothing was persisted." });
        },
        onError: (err) => {
          const e = err as ApiError;
          if (e.status === 409) {
            toast.error("This content has no ok profile.", {
              description: `Profile it first: uv run python -m app.cli profile-content --content-id ${contentId}`,
            });
          } else if (e.status === 502) {
            toast.error("The assessor could not produce a verdict.", {
              description: `${e.message} — if it was transient (LLM hiccup), just run it again.`,
            });
          } else {
            toast.error("The dry run failed.", { description: e.message });
          }
        },
      },
    );
  }

  if (contents.isLoading || profiles.isLoading || instruments.isLoading || packages.isLoading) {
    return <LoadingState />;
  }
  const loadError = contents.error ?? profiles.error ?? instruments.error ?? packages.error;
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
                        <TableCell className="font-medium">{content.external_id}</TableCell>
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
                              <p className="text-xs text-muted-foreground">
                                Profile it first:{" "}
                                <code className="rounded bg-muted px-1">
                                  uv run python -m app.cli profile-content --content-id{" "}
                                  {content.content_id}
                                </code>
                              </p>
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
            <Button onClick={run} disabled={!ready}>
              {preview.isPending ? <Spinner className="mr-2" /> : null}
              {preview.isPending ? "Running — LLM criteria take a while…" : "Run dry evaluation"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Nothing is persisted: no evaluation, no judgment, no events.
            </p>
          </div>
          {result ? <PreviewResults result={result} /> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function packageLabel(assessorPackage: AssessorPackageResponse): string {
  const total =
    assessorPackage.executes.length + Object.keys(assessorPackage.abstains).length;
  const llm = assessorPackage.uses_llm ? " · LLM" : "";
  return `${assessorPackage.display_name} — ${assessorPackage.instrument_id} (executes ${assessorPackage.executes.length}/${total}${llm})`;
}

// ------------------------------------------------------------------------- results

function PreviewResults({ result }: { result: PreviewEvaluationResponse }) {
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
          <Badge key={state} variant={OUTCOME_VARIANT[state]}>
            {state} · {partition.get(state)}
          </Badge>
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
              <TableRow key={outcome.criterion_id}>
                <TableCell className="font-mono text-xs">{outcome.criterion_id}</TableCell>
                <TableCell>
                  <Badge variant={OUTCOME_VARIANT[outcome.outcome]}>{outcome.outcome}</Badge>
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
                <Badge variant={CLAIM_VARIANT[claim.status]}>{claim.status}</Badge>
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
    </div>
  );
}

function OutcomeEvidence({ outcome }: { outcome: PreviewOutcome }) {
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
