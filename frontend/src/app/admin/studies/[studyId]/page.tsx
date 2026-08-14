"use client";

import { use, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowLeft,
  Check,
  FileCheck,
  ListChecks,
  Play,
  Square,
} from "lucide-react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Dialog } from "@/components/ui/dialog";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { StudyStatusBadge } from "@/components/admin/study-status";
import { StudyReportSection } from "@/components/admin/study-report/report-section";
import { ApiError } from "@/lib/api/client";
import {
  useAssessorPackages,
  useBriefs,
  useCancelStudyEvaluation,
  useComposeStudyDataset,
  useInstruments,
  useOpenStudy,
  usePinStudyInstrument,
  usePublishStudy,
  useStartStudyEvaluation,
  useStudy,
  useStudyEvaluationRun,
  useStudyEvaluations,
  useStudyFitness,
  useStudyReadiness,
} from "@/lib/api/hooks";
import type {
  BatchCourseStatus,
  BatchRun,
  BatchRunStatus,
  FitnessLevel,
  StudyEvaluations,
  StudyFitness,
  StudyReadiness,
  StudyResponse,
  Uuid,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** Everything one study needs doing happens here, in the order a round actually goes:
 *  set it up, evaluate it, sign the report off. The list is a list. */
export default function StudyDetailPage({
  params,
}: {
  params: Promise<{ studyId: Uuid }>;
}) {
  const { studyId } = use(params);
  const { data: study, isLoading, error } = useStudy(studyId);
  // Hoisted: the evaluation card and the publish card must quote the same two numbers.
  const evaluations = useStudyEvaluations(studyId);
  const readiness = useStudyReadiness(studyId);
  const fitness = useStudyFitness(studyId);

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!study) return <EmptyState title="Study not found" />;

  // A study before its opening has one job, an open one another, and a published one none
  // at all — every card below appears only while it has something a reader can act on.
  const inSetup = study.status === "declared" || study.status === "prepared";
  const published = study.status === "published";

  return (
    <div className="max-w-5xl space-y-6">
      <StudyHeader study={study} />

      {inSetup ? <SetupCard study={study} /> : null}

      {/* Evaluating and publishing are what an OPEN study is for. Once it is published a
          batch is refused and the report already states how many judgments it used, so the
          card would be a count you have and a paragraph about an act you cannot perform. */}
      {study.status === "open" ? (
        <>
          <EvaluationCard study={study} evaluations={evaluations.data ?? null} />
          <PublishCard study={study} evaluations={evaluations.data ?? null} />
        </>
      ) : null}

      {/* Readable before the irreversible act: publishing freezes a report, it does not
          reveal one. Not while still being set up, though — there is nothing to report yet
          and the setup card is the whole job. */}
      {inSetup ? null : <StudyReportSection study={study} />}

      {/* Below the phase it informs, never above it, and never on a published study: it is
          computed from TODAY's ratifications and adapters, so on a frozen report it can
          contradict the document it sits next to. */}
      {!published && readiness.data ? <ReadinessPanel readiness={readiness.data} /> : null}

      {/* Apart from the report on purpose (ADR-0023 §11): the juxtaposition is useful, the
          conflation is not — the report publishes no aggregate score, and this denominator
          is not the report's. */}
      {fitness.data ? <FitnessPanel fitness={fitness.data} /> : null}
    </div>
  );
}

function StudyHeader({ study }: { study: StudyResponse }) {
  return (
    <div>
      <Link
        href="/admin/studies"
        className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Studies
      </Link>
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{study.purpose}</h1>
        <StudyStatusBadge status={study.status} />
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {study.instrument_version_id ?? "no instrument pinned"} · {study.brief_ids.length} briefs
        → {study.content_ids.length} courses
      </p>
    </div>
  );
}

function actError(err: unknown) {
  const e = err as ApiError;
  if (e.status === 409) {
    toast.error("The study's state refuses this act.", { description: e.message });
  } else if (e.status === 422) {
    toast.error("The act is not possible yet.", { description: e.message });
  } else {
    toast.error("The act failed.", { description: e.message });
  }
}

// ------------------------------------------------------------------------------ setup

/** The three acts that make a study runnable, as three steps instead of three buttons
 *  scattered across a list. Their order is the domain's: the instrument is pinned before
 *  opening and never after, and opening fixes the dataset. */
function SetupCard({ study }: { study: StudyResponse }) {
  const pinned = study.instrument_version_id !== null;
  const composed = study.content_ids.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <ListChecks className="h-4 w-4 text-muted-foreground" /> Setup
          <span className="text-xs font-normal text-muted-foreground">
            three steps, in order — the last one freezes the dataset
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6 text-sm">
        <SetupStep
          n={1}
          done={pinned}
          title="Pin the instrument"
          hint="Which published instrument version this study judges against. Pinned once and never changed: what a study measured has to stay knowable."
        >
          {pinned ? (
            <p className="text-muted-foreground">
              Pinned: <code>{study.instrument_version_id}</code>
            </p>
          ) : (
            <PinStep study={study} />
          )}
        </SetupStep>

        <SetupStep
          n={2}
          done={composed}
          title="Compose the dataset"
          hint="Briefs select the courses registered from them. Replaceable until the study opens, and fixed forever after."
        >
          <ComposeStep study={study} />
        </SetupStep>

        <SetupStep
          n={3}
          done={false}
          title="Open the study"
          hint="Opening freezes the dataset and lets the batch run. There is no un-opening."
        >
          <OpenStep study={study} pinned={pinned} composed={composed} />
        </SetupStep>
      </CardContent>
    </Card>
  );
}

function SetupStep({
  n,
  title,
  hint,
  done,
  children,
}: {
  n: number;
  title: string;
  hint: string;
  done: boolean;
  children: ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <span
        className={cn(
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold",
          done ? "border-emerald-600 bg-emerald-600 text-white" : "text-muted-foreground",
        )}
      >
        {done ? <Check className="h-3.5 w-3.5" /> : n}
      </span>
      <div className="min-w-0 flex-1 space-y-2">
        <p className="font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
        {children}
      </div>
    </div>
  );
}

function PinStep({ study }: { study: StudyResponse }) {
  const { data: instruments } = useInstruments();
  const pin = usePinStudyInstrument();
  const [selected, setSelected] = useState("");
  const published = (instruments ?? []).filter((i) => i.status === "published");

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={selected} onChange={(e) => setSelected(e.target.value)} className="w-72">
        <option value="">Pin a published instrument…</option>
        {published.map((i) => (
          <option key={i.instrument_version_id} value={i.instrument_version_id}>
            {i.instrument_version_id}
          </option>
        ))}
      </Select>
      <Button
        size="sm"
        variant="outline"
        disabled={!selected || pin.isPending}
        onClick={() =>
          pin.mutate(
            { studyId: study.study_id, body: { instrument_version_id: selected } },
            {
              onSuccess: () => toast.success("Instrument pinned — once and forever."),
              onError: actError,
            },
          )
        }
      >
        {pin.isPending ? <Spinner /> : null} Pin
      </Button>
    </div>
  );
}

function ComposeStep({ study }: { study: StudyResponse }) {
  const [open, setOpen] = useState(false);
  const { data: briefs } = useBriefs();
  const compose = useComposeStudyDataset();
  const [selected, setSelected] = useState<Uuid[]>(study.brief_ids);
  const composed = study.content_ids.length > 0;

  function toggle(id: Uuid) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((b) => b !== id) : [...prev, id]));
  }

  return (
    <>
      <p className="text-muted-foreground">
        {composed
          ? `${study.brief_ids.length} brief${study.brief_ids.length === 1 ? "" : "s"} → ${study.content_ids.length} course${study.content_ids.length === 1 ? "" : "s"}.`
          : "No briefs picked yet."}
      </p>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        {composed ? "Change the dataset" : "Compose the dataset"}
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Compose the dataset"
        description="Briefs select the registered contents generated from them. The dataset stays replaceable until the study opens."
      >
        {!briefs || briefs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No briefs registered yet. Briefs arrive mechanically when contents with a
            syllabus are registered (ADR-0022), or manually in /admin/briefs.
          </p>
        ) : (
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {briefs.map((brief) => (
              <li key={brief.brief_id}>
                <label className="flex cursor-pointer items-start gap-2 rounded border p-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.includes(brief.brief_id)}
                    onChange={() => toggle(brief.brief_id)}
                    className="mt-1"
                  />
                  <span className="line-clamp-2">{brief.brief}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={compose.isPending}
            onClick={() =>
              compose.mutate(
                { studyId: study.study_id, body: { brief_ids: selected } },
                {
                  onSuccess: (updated) => {
                    setOpen(false);
                    toast.success(
                      `Dataset composed: ${updated.content_ids.length} courses from ${updated.brief_ids.length} briefs.`,
                    );
                  },
                  onError: actError,
                },
              )
            }
          >
            {compose.isPending ? <Spinner /> : null} Compose
          </Button>
        </div>
      </Dialog>
    </>
  );
}

function OpenStep({
  study,
  pinned,
  composed,
}: {
  study: StudyResponse;
  pinned: boolean;
  composed: boolean;
}) {
  const openStudy = useOpenStudy();
  return (
    <>
      <Button
        size="sm"
        disabled={!pinned || !composed || openStudy.isPending}
        onClick={() =>
          openStudy.mutate(
            { studyId: study.study_id },
            {
              onSuccess: () =>
                toast.success("Study open.", {
                  description: "The dataset is frozen. Next: evaluate it.",
                }),
              onError: actError,
            },
          )
        }
      >
        {openStudy.isPending ? <Spinner /> : null} Open the study
      </Button>
      {!pinned || !composed ? (
        <p className="text-xs text-muted-foreground">
          Do steps 1 and 2 first: a study opens onto a pinned instrument and a non-empty
          dataset.
        </p>
      ) : null}
    </>
  );
}

// ------------------------------------------------------------------ evaluation (ADR-0040)

const RUN_BADGE: Record<BatchRunStatus, BadgeProps["variant"]> = {
  running: "default",
  done: "success",
  cancelled: "outline",
  failed: "destructive",
  // The runner itself broke — a malfunction, never a verdict (the calibration palette).
  refused: "malfunction",
};

const COURSE_BADGE: Record<BatchCourseStatus, BadgeProps["variant"]> = {
  evaluated: "success",
  skipped: "secondary",
  failed: "destructive",
  cancelled: "outline",
};

/** `skipped` is a backend word for a good outcome: this assessor had already judged the
 *  course, so the run did not pay for it again. Shown as a bare status it reads as a
 *  failure, and it was the one line that made resuming a batch look like a bug. */
const COURSE_LABEL: Record<BatchCourseStatus, string> = {
  evaluated: "evaluated",
  skipped: "already judged",
  failed: "failed",
  cancelled: "not reached",
};

/** How much of the dataset carries a judgment — which decides what running the batch even
 *  means: a first pass, resuming an interrupted one, or replacing what is there. */
type EvaluationPhase = "none" | "partial" | "all";

const PHASE_BADGE: Record<EvaluationPhase, BadgeProps["variant"]> = {
  none: "outline",
  partial: "warning",
  all: "success",
};

function evaluateLabel(phase: EvaluationPhase, remaining: number): string {
  const labels: Record<EvaluationPhase, string> = {
    none: "Evaluate the dataset",
    partial: `Evaluate the remaining ${remaining}`,
    all: "Re-evaluate…",
  };
  return labels[phase];
}

function seconds(ms: number): string {
  return ms >= 60_000 ? `${Math.round(ms / 60_000)} min` : `${Math.round(ms / 1000)} s`;
}

/** Starting, watching and stopping a batch (ADR-0040), plus the count that outlives it.
 *
 * The durable count comes from the database, so it is still right after a restart and
 * counts a batch someone ran from the CLI. The live half exists only while this backend is
 * running one. */
function EvaluationCard({
  study,
  evaluations,
}: {
  study: StudyResponse;
  evaluations: StudyEvaluations | null;
}) {
  const [watching, setWatching] = useState<Uuid | null>(null);
  const run = useStudyEvaluationRun(study.study_id, watching);
  const cancel = useCancelStudyEvaluation(study.study_id);

  // The newest run this backend remembers is what to show when the page is opened again
  // while one is going — a reload must not lose sight of a batch that is still spending.
  const latest = evaluations?.runs[0] ?? null;
  const shown = run.data ?? latest;
  useEffect(() => {
    if (watching === null && latest?.status === "running") setWatching(latest.run_id);
  }, [latest, watching]);

  const running = shown?.status === "running";
  const courses = evaluations?.courses ?? study.content_ids.length;
  const judged = evaluations?.evaluated ?? 0;
  const remaining = Math.max(courses - judged, 0);
  const phase: EvaluationPhase = judged === 0 ? "none" : judged < courses ? "partial" : "all";
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
          {evaluations ? (
            <Badge variant={PHASE_BADGE[phase]}>
              {judged} of {courses} judged
            </Badge>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {evaluations ? (
          <ProgressLine
            phase={phase}
            judged={judged}
            courses={courses}
            instrument={evaluations.instrument_version_id}
            canPublish={study.status === "open"}
          />
        ) : null}

        {blocked ? (
          <p className="text-muted-foreground">Nothing to evaluate yet: {blocked}.</p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <StartEvaluation
              study={study}
              courses={courses}
              remaining={remaining}
              phase={phase}
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

        {/* Keyed by run: `CollapsibleSection` reads `defaultOpen` once, at mount. A new run
            remounts this and re-reads it, while within one run the reader's own choice
            survives the status changing under them. */}
        {shown ? <RunProgress key={shown.run_id} run={shown} /> : null}
      </CardContent>
    </Card>
  );
}

/** What running the batch would do next, said before it is run rather than discovered
 *  afterwards from a table full of `skipped`. */
function ProgressLine({
  phase,
  judged,
  courses,
  instrument,
  canPublish,
}: {
  phase: EvaluationPhase;
  judged: number;
  courses: number;
  instrument: string | null;
  canPublish: boolean;
}) {
  const under = instrument ? (
    <>
      {" "}
      under <code>{instrument}</code>
    </>
  ) : null;

  return (
    <>
      {phase === "none" ? (
        <p className="text-muted-foreground">
          No course carries a judgment{under} yet. Running the batch evaluates all {courses}.
        </p>
      ) : phase === "partial" ? (
        <p className="text-muted-foreground">
          {judged} of {courses} courses already carry a judgment{under}. Running the batch
          again evaluates only the {courses - judged} that do not: it resumes an interrupted
          round rather than repeating it, and pays for no LLM call twice.
        </p>
      ) : (
        <p className="text-muted-foreground">
          All {courses} courses carry a judgment{under}. Running the batch again would skip
          every one of them and cost nothing — to <em>replace</em> those judgments instead,
          tick “Re-evaluate” in the dialog, which spends the calls again.
          {canPublish ? " Publishing is what turns these judgments into a report." : ""}
        </p>
      )}

      {/* The count is taken per instrument version and the skip is taken per assessor, so
          the two can disagree. Saying so costs a sentence; a number nobody can trust costs
          more. */}
      {judged > 0 ? (
        <p className="text-xs text-muted-foreground">
          Counted by instrument version, not by assessor: a course judged by any ratified
          assessor counts here, while a run skips only what the assessor you pick judged
          itself. Where they differ, the run evaluates more than this number suggests.
        </p>
      ) : null}
    </>
  );
}

function RunProgress({ run }: { run: BatchRun }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <Badge variant={RUN_BADGE[run.status]}>{run.status}</Badge>
        <span className="tabular-nums">
          {run.done} of {run.total} courses · {run.evaluated} evaluated
          {run.failed > 0 ? ` · ${run.failed} failed` : ""}
          {run.skipped > 0 ? ` · ${run.skipped} already judged` : ""}
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

      {run.skipped > 0 ? (
        <p className="rounded bg-muted/40 p-2 text-xs text-muted-foreground">
          {run.skipped} of {run.total} course{run.skipped === 1 ? " was" : "s were"} skipped:
          this assessor had already judged {run.skipped === 1 ? "it" : "them"} under{" "}
          <code>{run.instrument_version_id}</code>, so the run did not pay for{" "}
          {run.skipped === 1 ? "it" : "them"} a second time. That is what makes running the
          batch again the way to resume an interrupted round.
        </p>
      ) : null}

      {run.courses.length > 0 ? (
        <CollapsibleSection
          title="Course by course"
          badge={`${run.courses.length} of ${run.total}`}
          defaultOpen={run.status === "running"}
          meta={
            <span className="flex flex-wrap items-center gap-2">
              <Badge variant="success">{run.evaluated} evaluated</Badge>
              {run.skipped > 0 ? (
                <Badge variant="secondary">{run.skipped} already judged</Badge>
              ) : null}
              {run.failed > 0 ? <Badge variant="destructive">{run.failed} failed</Badge> : null}
            </span>
          }
        >
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
                    <Badge variant={COURSE_BADGE[course.status]}>
                      {COURSE_LABEL[course.status]}
                    </Badge>
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
        </CollapsibleSection>
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
  remaining,
  phase,
  disabled,
  onStarted,
}: {
  study: StudyResponse;
  courses: number;
  remaining: number;
  phase: EvaluationPhase;
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
      {/* Secondary once there is nothing left to judge: re-running is a repair, not the
          thing to do next. */}
      <Button
        size="sm"
        variant={phase === "all" ? "outline" : "default"}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        <Play className="h-3.5 w-3.5" /> {evaluateLabel(phase, remaining)}
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
            {phase === "all" && !reEvaluate ? (
              <p className="rounded bg-muted/40 p-2 text-sm text-muted-foreground">
                Every course in this dataset already carries a judgment. As it stands this
                run skips all {courses} of them and spends nothing. Tick “Re-evaluate” below
                to judge them again — that replaces the judgments and spends the calls
                again.
              </p>
            ) : null}
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
                  For repairing a course that finished degraded: a criterion that errored is
                  this run&apos;s failure, not the course&apos;s. It replaces the previous
                  judgment rather than adding to it, so it never samples the judge — that is
                  what a calibration dry run is for. Off by default, which is what makes
                  running the batch again the way to resume an interrupted one.
                </span>
              </span>
            </label>
            {/* "Up to", because the count this is derived from is taken per instrument
                version while the skip is taken per assessor. */}
            <p className="text-xs text-muted-foreground">
              {reEvaluate
                ? `All ${courses} course${courses === 1 ? "" : "s"} will be evaluated again`
                : `Up to ${remaining} of ${courses} course${courses === 1 ? "" : "s"} will be evaluated — the rest are already judged and get skipped`}
              {chosen?.uses_llm && (reEvaluate || remaining > 0)
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

// ---------------------------------------------------------------------- publish

/** Signing off, next to the judgments being signed off — and saying how many courses carry
 *  none, because that is the caveat about to be frozen into the report. */
function PublishCard({
  study,
  evaluations,
}: {
  study: StudyResponse;
  evaluations: StudyEvaluations | null;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const courses = evaluations?.courses ?? study.content_ids.length;
  const unjudged = Math.max(courses - (evaluations?.evaluated ?? 0), 0);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2 text-base">
            <FileCheck className="h-4 w-4 text-muted-foreground" /> Publish the report
            {unjudged > 0 ? (
              <Badge variant="warning">
                {unjudged} course{unjudged === 1 ? "" : "s"} unjudged
              </Badge>
            ) : (
              <Badge variant="success">every course judged</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-muted-foreground">
            {unjudged === 0
              ? "Every course carries a judgment. Publishing composes the report from them, records exactly which ones it used, and never changes again."
              : `Publishing composes the report from the judgments that exist at that moment. ${unjudged} of ${courses} course${unjudged === 1 ? " carries" : "s carry"} none yet, and would be published as a caveat — visibly. Publishing with caveats is legitimate; publishing silently is impossible.`}
          </p>
          <Button
            variant={unjudged > 0 ? "outline" : "default"}
            onClick={() => setConfirmOpen(true)}
          >
            Publish…
          </Button>
        </CardContent>
      </Card>
      {/* Outside the Card, for the reason the assessors page states: nothing that could
          unmount may take an in-flight act with it. */}
      <PublishDialog
        study={study}
        courses={courses}
        unjudged={unjudged}
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
      />
    </>
  );
}

function PublishDialog({
  study,
  courses,
  unjudged,
  open,
  onClose,
}: {
  study: StudyResponse;
  courses: number;
  unjudged: number;
  open: boolean;
  onClose: () => void;
}) {
  const publish = usePublishStudy();

  return (
    <Dialog open={open} onClose={onClose} title={`Publish "${study.purpose}"?`}>
      <p className="text-sm text-muted-foreground">
        Publishing is a human act and it is irreversible: the report is composed from the
        current judgments, records exactly which ones it used, and never changes again.
        Caveats — insufficient evidence, unknown generators, unaccepted adapters — are
        published with it, visibly: publishing with caveats is legitimate; publishing
        silently is impossible.
      </p>
      {unjudged > 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          It will record {unjudged} of {courses} courses as carrying no judgment. That caveat
          is part of the report and cannot be removed afterwards — evaluating them first is
          still possible; publishing is not undoable.
        </p>
      ) : null}
      <div className="mt-4 flex justify-end gap-2 pt-2">
        <Button variant="outline" onClick={onClose} disabled={publish.isPending}>
          Cancel
        </Button>
        <Button
          disabled={publish.isPending}
          onClick={() =>
            publish.mutate(
              { studyId: study.study_id },
              {
                onSuccess: () => {
                  onClose();
                  toast.success("Study published — the report is immutable.");
                },
                onError: (err) => {
                  onClose();
                  actError(err);
                },
              },
            )
          }
        >
          {publish.isPending ? <Spinner /> : null} Publish permanently
        </Button>
      </div>
    </Dialog>
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
  // The qualities exist the moment an instrument is pinned, each of them `null` — so
  // `hasStudyLevel` was never the question a reader is asking. This is.
  const judged = fitness.contents.filter((content) => content.judged).length;

  return (
    // Closed, and headed by the question it answers rather than by its own name. It sits
    // apart from the report on purpose (ADR-0023 §11) — the juxtaposition is useful, the
    // conflation is not, and the two use different denominators. A closed section is the
    // cheapest way to say "read the report first": one asks what is wrong with these
    // courses, the other asks whether the generator is improving between rounds.
    <CollapsibleSection
      title="Is the generator getting better?"
      badge="optimization signal — not a judgment, and not part of the report"
      defaultOpen={false}
      className="border-dashed bg-muted/10"
      contentClassName="space-y-4 text-sm"
      meta={
        hasStudyLevel && judged > 0 && judged < fitness.contents.length ? (
          <Badge variant="warning">
            {judged} of {fitness.contents.length} courses judged
          </Badge>
        ) : null
      }
    >
      <div className="space-y-4 text-sm">
        {fitness.gaps.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {fitness.gaps.map((gap) => (
              <Badge key={gap.gap} variant="outline">
                {gap.gap.replaceAll("_", " ")}
              </Badge>
            ))}
          </div>
        ) : null}

        {!hasStudyLevel ? (
          <p className="text-muted-foreground">
            Nothing to measure yet: the study needs a pinned instrument and a dataset.
          </p>
        ) : judged === 0 ? (
          // One honest line instead of a grid of `undefined`. The rule that forbids a zero
          // here forbids printing a table of nothing and calling it a reading.
          <p className="text-muted-foreground">
            Undefined — none of the {fitness.contents.length} course
            {fitness.contents.length === 1 ? "" : "s"} carries a judgment yet, so every
            quality has an empty denominator. Undefined is not zero: a zero would say
            everything measurable failed, when nothing was measurable. Evaluate the dataset
            and this fills in.
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              Formula v{fitness.formulaVersion} · passed over (passed + failed + no
              evidence). Not assessed, not applicable and execution errors stay out of the
              denominator, so values computed under different assessor coverage — or runs
              with different execution-error counts — are not comparable.
            </p>

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
        )}
      </div>
    </CollapsibleSection>
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

/** What this round will not be able to answer — a question worth asking only while the
 *  answers do not exist yet.
 *
 *  Closed when it has nothing to report, because a whole panel saying "no gaps" is a panel
 *  that teaches the reader to skip it. Open when there are gaps, which is when it is the
 *  most useful thing on the page. */
function ReadinessPanel({ readiness }: { readiness: StudyReadiness }) {
  const claimGaps = readiness.claims.filter((c) => c.gaps.length > 0);
  const gaps = readiness.studyGaps.length + claimGaps.length;

  return (
    <CollapsibleSection
      title="Can this round answer what it asks?"
      badge="informs, never blocks"
      defaultOpen={gaps > 0}
      contentClassName="space-y-3 text-sm"
      meta={
        gaps > 0 ? (
          <Badge variant="warning">
            {gaps} gap{gaps === 1 ? "" : "s"}
          </Badge>
        ) : (
          <Badge variant="success">no gaps</Badge>
        )
      }
    >
      <div className="space-y-3 text-sm">
        {readiness.studyGaps.length === 0 && claimGaps.length === 0 ? (
          <p className="text-muted-foreground">
            Every claim has criteria, every criterion has a datum in this dataset&apos;s
            formats, and an assessor has ratified the pinned version — the study can run end
            to end.
          </p>
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
      </div>
    </CollapsibleSection>
  );
}
