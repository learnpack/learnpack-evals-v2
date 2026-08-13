"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Info, Play, Square, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import {
  useAssessorPackages,
  useCancelStudyEvaluation,
  useStartStudyEvaluation,
  useStudy,
  useStudyEvaluationRun,
  useStudyEvaluations,
  useStudyFitness,
  useStudyReadiness,
  useStudyReport,
} from "@/lib/api/hooks";
import type {
  BatchCourseStatus,
  BatchRun,
  FitnessLevel,
  StudyFitness,
  StudyReadiness,
  StudyReport,
  StudyReportContent,
  StudyReportGenerator,
  StudyResponse,
  Uuid,
} from "@/lib/api/types";

export default function StudyDetailPage({
  params,
}: {
  params: Promise<{ studyId: Uuid }>;
}) {
  const { studyId } = use(params);
  const { data: study, isLoading, error } = useStudy(studyId);
  const readiness = useStudyReadiness(studyId);
  const report = useStudyReport(studyId, study?.status === "published");
  const fitness = useStudyFitness(studyId);

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!study) return <EmptyState title="Study not found" />;

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <Link
          href="/admin/studies"
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Studies
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{study.purpose}</h1>
          <Badge>{study.status}</Badge>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {study.instrument_version_id ?? "no instrument pinned"} · {study.brief_ids.length}{" "}
          briefs → {study.content_ids.length} contents
        </p>
      </div>

      {readiness.data ? <ReadinessPanel readiness={readiness.data} /> : null}

      <EvaluationPanel study={study} />

      {study.status === "published" ? (
        report.isLoading ? (
          <LoadingState label="Loading the report…" />
        ) : report.data ? (
          <ReportView report={report.data.report} />
        ) : null
      ) : (
        <EmptyState
          title="No report yet"
          hint="The report is composed at publish and immutable afterwards."
        />
      )}

      {/* Apart from the report on purpose (ADR-0023 §11): the juxtaposition is useful, the
          conflation is not — the report publishes no aggregate score, and this denominator
          is not the report's. */}
      {fitness.data ? <FitnessPanel fitness={fitness.data} /> : null}
    </div>
  );
}

// ------------------------------------------------------------------ evaluation (ADR-0040)

const COURSE_BADGE: Record<BatchCourseStatus, "default" | "secondary" | "outline"> = {
  evaluated: "default",
  skipped: "secondary",
  failed: "outline",
  cancelled: "outline",
};

function seconds(ms: number): string {
  return ms >= 60_000 ? `${Math.round(ms / 60_000)} min` : `${Math.round(ms / 1000)} s`;
}

/** Starting, watching and stopping a batch (ADR-0040), plus the count that outlives it.
 *
 * The durable count comes from the database, so it is still right after a restart and
 * counts a batch someone ran from the CLI. The live half exists only while this backend is
 * running one. */
function EvaluationPanel({ study }: { study: StudyResponse }) {
  const evaluations = useStudyEvaluations(study.study_id);
  const [watching, setWatching] = useState<Uuid | null>(null);
  const run = useStudyEvaluationRun(study.study_id, watching);
  const cancel = useCancelStudyEvaluation(study.study_id);

  // The newest run this backend remembers is what to show when the page is opened again
  // while one is going — a reload must not lose sight of a batch that is still spending.
  const latest = evaluations.data?.runs[0] ?? null;
  const shown = run.data ?? latest;
  useEffect(() => {
    if (watching === null && latest?.status === "running") setWatching(latest.run_id);
  }, [latest, watching]);

  const running = shown?.status === "running";
  const blocked =
    !study.instrument_version_id
      ? "no instrument pinned"
      : study.content_ids.length === 0
        ? "no dataset composed"
        : study.status !== "open"
          ? `the study is ${study.status} — a batch evaluates an open study`
          : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <Play className="h-4 w-4 text-muted-foreground" /> Evaluation
          {evaluations.data ? (
            <span className="text-xs font-normal text-muted-foreground">
              {evaluations.data.evaluated} of {evaluations.data.courses} courses judged
              {evaluations.data.instrument_version_id
                ? ` under ${evaluations.data.instrument_version_id}`
                : ""}
            </span>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {blocked ? (
          <p className="text-muted-foreground">Nothing to evaluate yet: {blocked}.</p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <StartEvaluation
              study={study}
              courses={evaluations.data?.courses ?? study.content_ids.length}
              disabled={running}
              onStarted={setWatching}
            />
            {running && shown ? (
              <Button
                size="sm"
                variant="outline"
                disabled={cancel.isPending}
                onClick={() =>
                  cancel.mutate(shown.run_id, {
                    onSuccess: () =>
                      toast.success("Cancelling", {
                        description:
                          "No further course starts. What finished stays evaluated; what was in flight persists nothing.",
                      }),
                    onError: (err) =>
                      toast.error("Could not cancel.", { description: (err as Error).message }),
                  })
                }
              >
                {cancel.isPending ? <Spinner /> : <Square className="h-3.5 w-3.5" />} Stop
              </Button>
            ) : null}
          </div>
        )}

        {shown ? <RunProgress run={shown} /> : null}
      </CardContent>
    </Card>
  );
}

function RunProgress({ run }: { run: BatchRun }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <Badge variant={run.status === "running" ? "default" : "secondary"}>{run.status}</Badge>
        <span className="tabular-nums">
          {run.done} of {run.total} courses · {run.evaluated} evaluated
          {run.failed > 0 ? ` · ${run.failed} failed` : ""}
          {run.skipped > 0 ? ` · ${run.skipped} skipped` : ""}
        </span>
        <span>{run.assessor}</span>
        <span className="tabular-nums">{seconds(run.elapsed_ms)} elapsed</span>
        {run.remaining_ms_estimate ? (
          <span className="tabular-nums">
            ~{seconds(run.remaining_ms_estimate[0])}–{seconds(run.remaining_ms_estimate[1])} left
          </span>
        ) : null}
      </div>

      {run.status === "running" && run.current_activity ? (
        <p className="truncate text-xs text-muted-foreground" title={run.current_activity}>
          <Spinner /> {run.current_activity}
        </p>
      ) : null}
      {run.error ? <p className="text-xs text-destructive">{run.error}</p> : null}

      {run.courses.length > 0 ? (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Course</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Took</TableHead>
                <TableHead className="text-right">LLM calls</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.courses.map((course) => (
                <TableRow key={course.content_id}>
                  <TableCell>
                    {course.external_id}
                    {course.cause ? (
                      <span
                        className="ml-2 text-xs text-muted-foreground"
                        title={course.cause}
                      >
                        {course.cause.length > 80
                          ? `${course.cause.slice(0, 80)}…`
                          : course.cause}
                      </span>
                    ) : null}
                  </TableCell>
                  <TableCell>
                    <Badge variant={COURSE_BADGE[course.status]}>{course.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {course.duration_ms ? seconds(course.duration_ms) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {course.llm_calls || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </div>
  );
}

/** The dialog states what is being committed to before it is: real LLM calls per course, on
 *  the backend's key. Only assessors that have RATIFIED the pinned version are offered —
 *  the others would be refused by the endpoint, and an option that cannot work is worse
 *  than no option (ADR-0019, ADR-0036's stance). */
function StartEvaluation({
  study,
  courses,
  disabled,
  onStarted,
}: {
  study: StudyResponse;
  courses: number;
  disabled: boolean;
  onStarted: (runId: Uuid) => void;
}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [reEvaluate, setReEvaluate] = useState(false);
  const packages = useAssessorPackages();
  const start = useStartStudyEvaluation(study.study_id);

  const eligible = (packages.data ?? []).filter((pkg) =>
    pkg.lineage_versions.some(
      (version) =>
        version.instrument_version_id === study.instrument_version_id && version.ratified,
    ),
  );
  const chosen = eligible.find((pkg) => `${pkg.name}:${pkg.version}` === selected);

  return (
    <>
      <Button size="sm" disabled={disabled} onClick={() => setOpen(true)}>
        <Play className="h-3.5 w-3.5" /> Evaluate the dataset
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Evaluate every course of this study"
        description="Each course is a real evaluation: it spends LLM calls on the backend's key and persists its judgment. It can be stopped at any time — what finished stays."
      >
        {eligible.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No assessor has ratified {study.instrument_version_id}. Ratifying is a human act
            (ADR-0019) and lives in /admin/assessors — without it no judgment may persist.
          </p>
        ) : (
          <div className="space-y-3">
            <ul className="space-y-2">
              {eligible.map((pkg) => {
                const key = `${pkg.name}:${pkg.version}`;
                return (
                  <li key={key}>
                    <label className="flex cursor-pointer items-start gap-2 rounded border p-2 text-sm">
                      <input
                        type="radio"
                        name="assessor"
                        checked={selected === key}
                        onChange={() => setSelected(key)}
                        className="mt-1"
                      />
                      <span>
                        {pkg.display_name}
                        <span className="ml-2 text-xs text-muted-foreground">
                          {pkg.executes.length} criteria executed
                          {pkg.uses_llm ? " · spends LLM calls" : " · no LLM calls"}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
            <label className="flex cursor-pointer items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={reEvaluate}
                onChange={(event) => setReEvaluate(event.target.checked)}
                className="mt-1"
              />
              <span>
                Re-evaluate courses this assessor already judged
                <span className="block text-xs text-muted-foreground">
                  Off by default, which is what makes running it again the way to resume an
                  interrupted batch.
                </span>
              </span>
            </label>
            <p className="text-xs text-muted-foreground">
              {courses} course{courses === 1 ? "" : "s"} in the dataset
              {chosen?.uses_llm
                ? " · each spends real LLM calls, so this costs money and minutes"
                : ""}
            </p>
          </div>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={!selected || start.isPending}
            onClick={() => {
              const [name, version] = (selected ?? "").split(":");
              start.mutate(
                { assessor_name: name, assessor_version: version, re_evaluate: reEvaluate },
                {
                  onSuccess: (started) => {
                    setOpen(false);
                    onStarted(started.run_id);
                    toast.success("Evaluating", {
                      description: "It reports as it goes, and can be stopped at any time.",
                    });
                  },
                  onError: (err) => {
                    const detail = (err as ApiError).message;
                    toast.error("Could not start.", { description: detail });
                  },
                },
              );
            }}
          >
            {start.isPending ? <Spinner /> : null} Evaluate
          </Button>
        </div>
      </Dialog>
    </>
  );
}

// --------------------------------------------------------------------- fitness

/** Undefined is shown as such. A zero here would say "everything measurable failed"
 *  when nothing was measurable — the lie the denominator rules exist to prevent. */
function FitnessValue({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-muted-foreground italic">undefined</span>;
  }
  return <span className="font-medium tabular-nums">{(value * 100).toFixed(0)}%</span>;
}

function FitnessLevelTable({ level }: { level: FitnessLevel }) {
  const dimensions = Object.entries(level.dimensions);
  const qualities = Object.entries(level.qualities);
  return (
    <div className="space-y-3">
      {dimensions.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {dimensions.map(([id, dimension]) => (
            <span key={id} className="rounded bg-muted/60 px-2 py-1 text-xs">
              {id} <FitnessValue value={dimension.fitness} />
              <span className="ml-1 text-muted-foreground">
                ({dimension.coverage.defined}/{dimension.coverage.qualities} qualities)
              </span>
            </span>
          ))}
        </div>
      ) : null}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Quality</TableHead>
              <TableHead>Fitness</TableHead>
              <TableHead className="text-right">Denominator</TableHead>
              <TableHead className="text-right">Excluded</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {qualities.map(([id, quality]) => (
              <TableRow key={id}>
                <TableCell>
                  {id}
                  {quality.dimensionId ? (
                    <span className="ml-2 text-xs text-muted-foreground">
                      {quality.dimensionId}
                    </span>
                  ) : null}
                </TableCell>
                <TableCell>
                  <FitnessValue value={quality.fitness} />
                </TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">
                  {quality.coverage.pass}/{quality.coverage.denominator}
                </TableCell>
                <TableCell className="text-right text-xs text-muted-foreground">
                  {quality.coverage.notAssessed} not assessed ·{" "}
                  {quality.coverage.notApplicable} n/a ·{" "}
                  {quality.coverage.executionError} errored
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function FitnessPanel({ fitness }: { fitness: StudyFitness }) {
  const hasStudyLevel = Boolean(fitness.study.qualities);
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <TrendingUp className="h-4 w-4 text-muted-foreground" /> Fitness
          <span className="text-xs font-normal text-muted-foreground">
            optimization signal — not a judgment, and not part of the report
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <p className="text-xs text-muted-foreground">
          Formula v{fitness.formulaVersion} · passed over (passed + failed + no evidence).
          Not assessed, not applicable and execution errors stay out of the denominator, so
          values computed under different assessor coverage — or runs with different
          execution-error counts — are not comparable.
        </p>

        {fitness.gaps.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {fitness.gaps.map((gap) => (
              <Badge key={gap.gap} variant="outline">
                {gap.gap.replaceAll("_", " ")}
              </Badge>
            ))}
          </div>
        ) : null}

        {hasStudyLevel ? (
          <>
            {fitness.generators.map((generator) => (
              <div key={generator.generatorVersionId} className="space-y-2">
                <p className="font-medium">
                  {generator.name ?? generator.generatorVersionId}
                  {generator.version ? ` ${generator.version}` : ""}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    {generator.contents} content{generator.contents === 1 ? "" : "s"} pooled
                  </span>
                </p>
                <FitnessLevelTable level={generator} />
              </div>
            ))}

            <ByBrief fitness={fitness} />

            <div className="space-y-2">
              <p className="font-medium">
                Whole study
                {fitness.unknownExclusions && fitness.unknownExclusions.length > 0 ? (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    {fitness.unknownExclusions.length} content
                    {fitness.unknownExclusions.length === 1 ? "" : "s"} with an unknown
                    generator: counted here, excluded from generator level
                  </span>
                ) : null}
              </p>
              <FitnessLevelTable level={fitness.study as FitnessLevel} />
            </div>

            <p className="text-xs text-muted-foreground">
              {fitness.assessorCoverage.ratifiedAssessors?.length ?? 0} ratified assessor(s)
              · {fitness.assessorCoverage.notAssessed ?? 0} criteria left unassessed
              · {fitness.assessorCoverage.executionErrors ?? 0} execution error(s)
            </p>
          </>
        ) : (
          <p className="text-muted-foreground">
            Nothing to measure yet: the study needs a pinned instrument and a dataset.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

/** The brief is a grouping axis, not a grain (ADR-0039): nothing here is a per-brief score.
 *  Courses generated from one commission sit together so their spread is readable — which is
 *  the whole reason several are generated from it, and what a pooled number would erase. */
function ByBrief({ fitness }: { fitness: StudyFitness }) {
  const dimensionIds = Object.keys(fitness.study.dimensions ?? {});
  const named = new Map(fitness.briefs.map((b) => [b.briefId, b]));
  const groups = new Map<string, StudyFitness["contents"]>();
  for (const content of fitness.contents) {
    const key = content.briefId ?? "";
    groups.set(key, [...(groups.get(key) ?? []), content]);
  }
  // Every commission of the recipe, including one that produced no course; the contents
  // without a derived brief (ADR-0022) group nowhere and are listed last.
  const keys = [
    ...fitness.briefs.map((b) => b.briefId).filter((id) => id !== ""),
    ...(groups.has("") ? [""] : []),
  ];
  if (keys.length === 0) return null;

  return (
    <div className="space-y-3">
      <p className="font-medium">
        By brief
        <span className="ml-2 text-xs font-normal text-muted-foreground">
          grouped, never pooled — one row per course, so repeats of a commission can be
          compared
        </span>
      </p>
      {keys.map((briefId) => {
        const brief = named.get(briefId);
        const courses = groups.get(briefId) ?? [];
        return (
          <div key={briefId || "unpaired"} className="space-y-1">
            <p className="text-sm">
              {briefId === "" ? (
                <span className="italic text-muted-foreground">no brief derived</span>
              ) : (
                <span className="max-w-xl truncate" title={brief?.brief ?? undefined}>
                  {brief?.brief ?? briefId}
                </span>
              )}
              <span className="ml-2 text-xs text-muted-foreground">
                {briefId === ""
                  ? null
                  : brief?.briefHash
                    ? `${brief.briefHash.slice(0, 12)}… · `
                    : "registered by hand · "}
                {courses.length} course{courses.length === 1 ? "" : "s"}
              </span>
            </p>
            {courses.length === 0 ? (
              <p className="text-xs italic text-muted-foreground">
                no course in this study answers this commission
              </p>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Course</TableHead>
                      {dimensionIds.map((id) => (
                        <TableHead key={id} className="text-right">
                          {id}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {courses.map((content) => (
                      <TableRow key={content.contentId}>
                        <TableCell>
                          {content.externalId}
                          {content.judged ? null : (
                            <span className="ml-2 text-xs italic text-muted-foreground">
                              not judged
                            </span>
                          )}
                        </TableCell>
                        {dimensionIds.map((id) => (
                          <TableCell key={id} className="text-right">
                            <FitnessValue value={content.dimensions[id]?.fitness ?? null} />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------- readiness

function ReadinessPanel({ readiness }: { readiness: StudyReadiness }) {
  const claimGaps = readiness.claims.filter((c) => c.gaps.length > 0);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Info className="h-4 w-4 text-muted-foreground" /> Readiness
          <span className="text-xs font-normal text-muted-foreground">
            informs, never blocks
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {readiness.studyGaps.length === 0 && claimGaps.length === 0 ? (
          <p className="text-muted-foreground">No gaps: the study can run end to end.</p>
        ) : null}
        {readiness.studyGaps.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {readiness.studyGaps.map((gap) => (
              <Badge key={gap.gap} variant="outline">
                {gap.gap.replaceAll("_", " ")}
                {gap.instrumentVersionId ? ` (${gap.instrumentVersionId})` : ""}
              </Badge>
            ))}
          </div>
        ) : null}
        {readiness.formats.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            {readiness.formats.map((f) => (
              <span key={f.packageFormat} className="mr-3">
                {f.packageFormat}: adapter {f.adapterVersion ?? "—"} ·{" "}
                {f.extractionAccepted === null
                  ? "no adapter"
                  : f.extractionAccepted
                    ? "extraction accepted"
                    : "extraction NOT accepted"}
              </span>
            ))}
          </p>
        ) : null}
        {claimGaps.map((claim) => (
          <div key={claim.claimId} className="rounded bg-muted/40 p-2">
            <span className="font-medium">{claim.claimId}</span>
            <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
              {claim.gaps.map((gap, i) => (
                <li key={i}>
                  {gap.gap.replaceAll("_", " ")}
                  {gap.criterionId ? ` — ${gap.criterionId}` : ""}
                  {gap.missingData ? ` (missing: ${gap.missingData.join(", ")})` : ""}
                  {gap.packageFormat ? ` [${gap.packageFormat}]` : ""}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------- report

const STATUS_COLOR: Record<string, "default" | "destructive" | "secondary"> = {
  supported: "default",
  refuted: "destructive",
  insufficient: "secondary",
};

function ReportView({ report }: { report: StudyReport }) {
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Published {new Date(report.publishedAt).toLocaleString()} · instrument{" "}
        {report.instrumentVersionId} · dataset of {report.dataset.size} ·{" "}
        {Object.keys(report.judgmentIdsUsed).length} judgments recorded
      </p>

      {report.generatorLevel.length > 0 ? (
        report.generatorLevel.map((generator) => (
          <GeneratorSection key={generator.generatorVersionId} generator={generator} />
        ))
      ) : (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            No generator-level accumulation: no content in the dataset carries a known
            generator version (see the caveats below).
          </CardContent>
        </Card>
      )}

      {report.contents.map((content) => (
        <ContentSection key={content.contentId} content={content} />
      ))}

      <CaveatsSection report={report} />
    </div>
  );
}

function GeneratorSection({ generator }: { generator: StudyReportGenerator }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Generator level — {generator.name ?? generator.generatorVersionId}{" "}
          {generator.version ?? ""}
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            {generator.contentsCounted} contents counted
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Claim</TableHead>
              <TableHead>Supported</TableHead>
              <TableHead>Refuted</TableHead>
              <TableHead>Insufficient</TableHead>
              <TableHead>Coverage</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {generator.perClaim.map((claim) => (
              <TableRow key={claim.claimId}>
                <TableCell title={claim.claimId}>{claim.statement}</TableCell>
                <TableCell>{claim.distribution.supported ?? 0}</TableCell>
                <TableCell>{claim.distribution.refuted ?? 0}</TableCell>
                <TableCell>{claim.distribution.insufficient ?? 0}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {claim.coverage.evaluated}/{claim.coverage.of}
                  {claim.excludedNotApplicable
                    ? ` · ${claim.excludedNotApplicable} n/a`
                    : ""}
                  {claim.notEvaluated ? ` · ${claim.notEvaluated} not evaluated` : ""}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function ContentSection({ content }: { content: StudyReportContent }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {content.externalId}
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            {content.packageFormat} ·{" "}
            {content.generatorVersionId ? "generator known" : "generator unknown"}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!content.judgmentId ? (
          <p className="text-sm text-muted-foreground">Not judged when published.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {(content.claims ?? []).map((claim) => (
                <Badge key={claim.claimId} variant={STATUS_COLOR[claim.status] ?? "secondary"}>
                  {claim.claimId}: {claim.status}
                  {claim.insufficiencyCause ? ` (${claim.insufficiencyCause})` : ""}
                </Badge>
              ))}
            </div>
            {(content.findings ?? []).length > 0 ? (
              <ul className="space-y-2 text-sm">
                {(content.findings ?? []).map((finding) => (
                  <li key={finding.findingId} className="rounded bg-muted/40 p-2">
                    <span className="font-medium">{finding.criterionId}</span> —{" "}
                    {finding.failureMode}
                    {finding.quote ? (
                      <blockquote className="mt-1 border-l-2 pl-2 text-xs text-muted-foreground">
                        “{finding.quote}”
                      </blockquote>
                    ) : (
                      <span className="mt-1 block text-xs italic text-muted-foreground">
                        no quote — {finding.quoteAbsentCause}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function CaveatsSection({ report }: { report: StudyReport }) {
  const caveats = report.caveats;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Caveats</CardTitle>
        <p className="text-xs text-muted-foreground">
          Always published with the report — publishing silently is impossible.
        </p>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <CaveatRow label="Insufficient evidence">
          {caveats.insufficientEvidence.length === 0
            ? "none"
            : caveats.insufficientEvidence
                .map((c) => `${c.claimId} (${c.cause})`)
                .join(" · ")}
        </CaveatRow>
        <CaveatRow label="Unresolved disagreements">
          {caveats.unresolvedDisagreements.length === 0
            ? "none (single automated assessor)"
            : `${caveats.unresolvedDisagreements.length}`}
        </CaveatRow>
        <CaveatRow label="Unknown-generator exclusions">
          {caveats.unknownExclusions.contentIds.length === 0
            ? "none"
            : `${caveats.unknownExclusions.contentIds.length} contents — ${caveats.unknownExclusions.note}`}
        </CaveatRow>
        <CaveatRow label="Unaccepted adapters">
          {caveats.unacceptedAdapters.length === 0
            ? "none"
            : caveats.unacceptedAdapters
                .map((a) => `${a.packageFormat} (${a.adapterVersion ?? "no adapter"})`)
                .join(" · ")}
        </CaveatRow>
        <CaveatRow label="Brief completeness">
          {caveats.briefCompleteness.length === 0
            ? "all briefs complete"
            : caveats.briefCompleteness
                .map((b) => `${b.origin ?? "manual"}: prompt not recorded`)
                .join(" · ")}
        </CaveatRow>
        <CaveatRow label="Contents without judgment">
          {caveats.contentsWithoutJudgment.length === 0
            ? "none"
            : `${caveats.contentsWithoutJudgment.length}`}
        </CaveatRow>
        <CaveatRow label="Execution errors">
          {(caveats.executionErrors?.perContent ?? []).length === 0
            ? "none"
            : `${caveats.executionErrors!.perContent.length} content(s), ` +
              `${caveats.executionErrors!.perContent.reduce((sum, c) => sum + c.count, 0)} ` +
              `criteria — ${caveats.executionErrors!.note}`}
        </CaveatRow>
        <CaveatRow label="Task-variable patterns">
          {caveats.taskVariablePatterns.status}: {caveats.taskVariablePatterns.reason}
        </CaveatRow>
      </CardContent>
    </Card>
  );
}

function CaveatRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <p>
      <span className="font-medium">{label}:</span>{" "}
      <span className="text-muted-foreground">{children}</span>
    </p>
  );
}
