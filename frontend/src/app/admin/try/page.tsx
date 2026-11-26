"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { TermHint } from "@/components/ui/term-hint";
import { ClaimStatusBadge } from "@/components/admin/claim-status";
import { AssessorChoice, InstrumentChoice } from "@/components/admin/measurement-choice";
import { OUTCOME_ORDER, OutcomeBadge } from "@/components/admin/outcome-badge";
import { OutcomeEvidence, RunFailure, RunProgress } from "@/components/admin/preview/run";
import { ExplainButton } from "@/components/explain/explain-button";
import type { ApiError } from "@/lib/api/client";
import {
  useAssessorPackages,
  useContents,
  useInstruments,
  useMatchings,
  usePreviewRun,
  useProfiles,
  useQualityReference,
  useStartPreviewRun,
} from "@/lib/api/hooks";
import { ratifiedFor } from "@/lib/assessor-eligibility";
import { courseLabel } from "@/lib/courses";
import type {
  InstrumentResponse,
  PreviewEvaluationResponse,
  QualityReferenceResponse,
  Uuid,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * One course, one instrument, one assessor, and nothing saved: the dry run Calibration
 * performs, offered as the way to see what evaluating a course looks like before running a
 * study.
 *
 * Narrower than Calibration on purpose. It offers published instruments that read the
 * course's format and assessors ratified against them, the same choices a study offers, and
 * chosen the same way, explicitly (ADR-0042). It shows the result the way a study's report
 * does: claims grouped by dimension, down to the evidence. The prompts, the model calls, the
 * reading against a panel and any instrument with any assessor stay in Calibration, which is
 * where an instrument is tuned.
 */
export default function TryOneCoursePage() {
  const contents = useContents();
  const profiles = useProfiles();
  const instruments = useInstruments();
  const packages = useAssessorPackages();
  const vocabulary = useQualityReference();
  const start = useStartPreviewRun();

  const [contentId, setContentId] = useState<Uuid | "">("");
  const [instrumentId, setInstrumentId] = useState("");
  const [assessorId, setAssessorId] = useState("");
  // The course and the instrument travel with the run, so the result is read against what
  // actually ran, whatever the selects say now.
  const [started, setStarted] = useState<{
    runId: Uuid;
    contentId: Uuid;
    instrument: InstrumentResponse;
  } | null>(null);
  const run = usePreviewRun(started?.runId ?? null);

  /** A course can be tried once it has been read: the dry run reads its profile. */
  const readable = useMemo(() => {
    const ok = new Set(
      (profiles.data ?? []).filter((p) => p.status === "ok").map((p) => p.content_id),
    );
    return (contents.data ?? []).filter((content) => ok.has(content.content_id));
  }, [contents.data, profiles.data]);

  const course = readable.find((content) => content.content_id === contentId);
  const format = course?.package_format ?? "";
  const matchings = useMatchings(instrumentId || null, format ? [format] : []);

  const status = run.data?.status;
  useEffect(() => {
    if (status === "done") toast.success("Finished.", { description: "Nothing was saved." });
    else if (status === "failed") toast.error("The run failed.", { description: "The reason is on the page." });
  }, [status]);

  if (
    contents.isLoading ||
    profiles.isLoading ||
    instruments.isLoading ||
    packages.isLoading
  ) {
    return <LoadingState />;
  }
  const loadError = contents.error ?? profiles.error ?? instruments.error ?? packages.error;
  if (loadError) return <ErrorState message={(loadError as Error).message} />;

  const instrumentsForFormat = (instruments.data ?? []).filter(
    (instrument) =>
      instrument.status === "published" &&
      instrument.bindings.some((binding) => binding.package_format === format),
  );
  const eligible = ratifiedFor(packages.data ?? [], instrumentId);
  const assessor = eligible.find((pkg) => pkg.assessor_id === assessorId);
  const instrument = instrumentsForFormat.find((i) => i.instrument_version_id === instrumentId);
  const running = start.isPending || status === "running";

  function chooseCourse(next: Uuid | "") {
    setContentId(next);
    // A result belongs to the course it ran on; another course clears it.
    setStarted(null);
    // A different format can make the chosen instrument unreadable: start the choice over.
    setInstrumentId("");
    setAssessorId("");
  }

  function chooseInstrument(next: string) {
    setInstrumentId(next);
    if (!ratifiedFor(packages.data ?? [], next).some((pkg) => pkg.assessor_id === assessorId)) {
      setAssessorId("");
    }
  }

  function runIt() {
    if (!contentId || !instrument || !assessor) return;
    setStarted(null);
    start.mutate(
      {
        content_id: contentId,
        instrument_version_id: instrument.instrument_version_id,
        assessor_name: assessor.name,
        assessor_version: assessor.version,
      },
      {
        onSuccess: (data) => setStarted({ runId: data.run_id, contentId, instrument }),
        onError: (err) =>
          toast.error("The run could not be started.", { description: (err as ApiError).message }),
      },
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Try one course</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          See how a single course does. Nothing is saved, so you can try as often as you like.
          To measure a whole batch and keep the result, start a study instead.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>What to try</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="max-w-xl space-y-1.5">
            <Label htmlFor="try-course">Course</Label>
            {readable.length === 0 ? (
              <EmptyState
                title="No course has been read yet"
                hint="Register courses first, from Evaluate courses or Courses. A course can be tried once its package has been read."
              />
            ) : (
              <Select
                id="try-course"
                value={contentId}
                onChange={(event) => chooseCourse(event.target.value as Uuid | "")}
              >
                <option value="">Choose a course…</option>
                {readable.map((content) => (
                  <option key={content.content_id} value={content.content_id}>
                    {courseLabel(content)} · {content.package_format}
                  </option>
                ))}
              </Select>
            )}
          </div>

          {course ? (
            <InstrumentChoice
              instruments={instrumentsForFormat}
              value={instrumentId}
              onChange={chooseInstrument}
            />
          ) : null}

          {course && instrumentId ? (
            <AssessorChoice
              assessors={eligible}
              matching={matchings.byFormat.get(format)}
              format={format}
              value={assessorId}
              onChange={setAssessorId}
            />
          ) : null}

          <div className="flex flex-wrap items-center gap-3 border-t pt-4">
            <Button onClick={runIt} disabled={!course || !instrument || !assessor || running}>
              {running ? <Spinner className="mr-2" /> : null}
              {running ? "Running… a model can take a while" : "Run it"}
            </Button>
            <ExplainButton topic="mechanisms">How an assessor decides</ExplainButton>
            {assessor?.uses_llm ? (
              <p className="text-xs text-muted-foreground">
                This assessor calls a model, so a run spends calls on the backend&apos;s key.
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {run.error ? <ErrorState message={(run.error as ApiError).message} /> : null}
      {run.data ? (
        <div className="space-y-4">
          <RunProgress run={run.data} />
          {run.data.error && started ? (
            <RunFailure error={run.data.error} contentId={started.contentId} />
          ) : null}
          {run.data.result && started ? (
            <TryResults
              result={run.data.result}
              instrument={started.instrument}
              vocabulary={vocabulary.data ?? []}
            />
          ) : null}
        </div>
      ) : null}

      <p className="text-xs text-muted-foreground">
        Tuning an instrument? <Link href="/admin/calibration" className="text-primary hover:underline">Calibration</Link>{" "}
        runs the same dry run with every model call shown, against any instrument and any
        assessor.
      </p>
    </div>
  );
}

/**
 * The run's result, read the way a study's report reads: claims by dimension, then quality,
 * each with its status, and its criteria with their evidence one click away. The grouping is
 * the instrument's frozen map (ADR-0023 §8); the names are the vocabulary's.
 */
function TryResults({
  result,
  instrument,
  vocabulary,
}: {
  result: PreviewEvaluationResponse;
  instrument: InstrumentResponse;
  vocabulary: QualityReferenceResponse[];
}) {
  const statusOf = new Map(result.claims.map((claim) => [claim.claim_id, claim.status]));
  const outcomeOf = new Map(result.outcomes.map((outcome) => [outcome.criterion_id, outcome]));
  const qualityName = new Map(vocabulary.map((q) => [q.quality_id, q.quality_name]));
  const dimensionName = new Map(
    vocabulary
      .filter((q) => q.dimension_id)
      .map((q) => [q.dimension_id as string, q.dimension_name ?? q.dimension_id]),
  );

  const groups: { dimensionId: string | null; claims: InstrumentResponse["claims"] }[] = [];
  for (const claim of instrument.claims) {
    const qualityId = claim.quality_ids[0];
    const dimensionId = qualityId ? (instrument.quality_dimensions[qualityId] ?? null) : null;
    let group = groups.find((g) => g.dimensionId === dimensionId);
    if (!group) {
      group = { dimensionId, claims: [] };
      groups.push(group);
    }
    group.claims.push(claim);
  }

  const partition = new Map<string, number>();
  for (const outcome of result.outcomes) {
    partition.set(outcome.outcome, (partition.get(outcome.outcome) ?? 0) + 1);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>{result.outcomes.length} criteria:</span>
          {OUTCOME_ORDER.filter((state) => partition.has(state)).map((state) => (
            <span key={state} className="flex items-center gap-1">
              <OutcomeBadge outcome={state} /> {partition.get(state)}
            </span>
          ))}
        </div>
        <span className="flex flex-wrap gap-3">
          <ExplainButton topic="ladder">How to read a claim</ExplainButton>
          <ExplainButton topic="outcomes">What each outcome means</ExplainButton>
        </span>
      </div>

      {groups.map((group) => (
        <section key={group.dimensionId ?? "none"} className="rounded-lg border bg-card">
          <h2 className="flex items-center border-b px-4 py-3 font-medium">
            {group.dimensionId
              ? (dimensionName.get(group.dimensionId) ?? group.dimensionId)
              : "Not grouped under a dimension"}
            <TermHint term="dimension" />
          </h2>
          <ul className="divide-y">
            {group.claims.map((claim) => (
              <ClaimResult
                key={claim.claim_id}
                statement={claim.statement}
                claimId={claim.claim_id}
                quality={qualityName.get(claim.quality_ids[0]) ?? claim.quality_ids[0] ?? null}
                status={statusOf.get(claim.claim_id) ?? null}
                criteria={instrument.criteria
                  .filter((criterion) => criterion.claim_ids.includes(claim.claim_id))
                  .map((criterion) => ({
                    id: criterion.criterion_id,
                    statement: criterion.statement ?? criterion.criterion_id,
                    outcome: outcomeOf.get(criterion.criterion_id) ?? null,
                  }))}
              />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ClaimResult({
  statement,
  claimId,
  quality,
  status,
  criteria,
}: {
  statement: string;
  claimId: string;
  quality: string | null;
  /** Null when every criterion under it does not apply to this format: left out. */
  status: "supported" | "refuted" | "insufficient" | null;
  criteria: {
    id: string;
    statement: string;
    outcome: PreviewEvaluationResponse["outcomes"][number] | null;
  }[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <li className="text-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-start gap-2 px-4 py-3 text-left hover:bg-accent/40"
      >
        <ChevronDown
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
            !open && "-rotate-90",
          )}
        />
        <span className="min-w-0 flex-1">
          <span className="block">{statement}</span>
          <span className="block text-xs text-muted-foreground">
            {quality ? `${quality} · ` : ""}
            <span className="font-mono">{claimId}</span>
          </span>
        </span>
        {status ? (
          <ClaimStatusBadge status={status} />
        ) : (
          <OutcomeBadge outcome="not_applicable" />
        )}
      </button>
      {open ? (
        <ul className="space-y-2 px-4 pb-3 pl-10">
          {criteria.map((criterion) => (
            <li key={criterion.id} className="space-y-1 rounded border bg-background p-2 text-xs">
              <div className="flex flex-wrap items-start gap-2">
                {criterion.outcome ? <OutcomeBadge outcome={criterion.outcome.outcome} /> : null}
                <span className="min-w-0 flex-1">{criterion.statement}</span>
              </div>
              <p className="font-mono text-[11px] text-muted-foreground">{criterion.id}</p>
              {criterion.outcome ? <OutcomeEvidence outcome={criterion.outcome} /> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}
