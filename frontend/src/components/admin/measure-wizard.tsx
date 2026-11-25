"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Check, Folder } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { TermHint } from "@/components/ui/term-hint";
import { BatchSummary } from "@/components/admin/batch-summary";
import { FolderBreadcrumb } from "@/components/admin/folder-breadcrumb";
import { NewGeneratorVersionDialog } from "@/components/admin/generator-version-dialog";
import {
  GeneratorVersionPicker,
  UNKNOWN_GENERATOR,
} from "@/components/admin/generator-version-picker";
import { AssessorChoice, InstrumentChoice } from "@/components/admin/measurement-choice";
import {
  useAssessorPackages,
  useContents,
  useGenerators,
  useGeneratorVersions,
  useInstruments,
  useMatchings,
} from "@/lib/api/hooks";
import { ratifiedFor } from "@/lib/assessor-eligibility";
import { declarationSignal, looksLikeSameGeneratorName } from "@/lib/generator-declaration";
import { REGISTRABLE, useImportBatch } from "@/lib/use-import-batch";
import { useSaveAndStart } from "@/lib/use-save-and-start";
import { groupByVersion } from "@/lib/versions";
import type { EditProvenance, ScanCandidate, ScanVerdict, Uuid } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/** Plain names for the formats a newcomer meets. A format with no entry shows its own name. */
const FORMAT_LABEL: Record<string, string> = {
  LearnpackV1: "Finished courses",
  LearnpackV2: "Drafts",
};

const VERDICT_LABEL: Record<ScanVerdict, string> = {
  new: "new",
  new_version: "new version",
  unchanged: "already registered",
  conflict: "conflict",
  unreadable: "not a course",
};

type Step = 1 | 2 | 3;

/**
 * Measuring a batch in three steps: the folder, how thorough, the start (ADR-0070).
 *
 * It runs on the same import and save logic as the long page at `/admin/measure/all`, so the
 * two cannot disagree about what an act does. What it changes is the order and the defaults:
 * one question per step, and only the questions with consequences asked at all. Those are
 * asked explicitly, never preselected: the generator (ADR-0024), the instrument and the
 * assessor (ADR-0042).
 */
export function MeasureWizard() {
  const batchImport = useImportBatch();
  const [step, setStep] = useState<Step>(1);
  // Set once the courses are registered as Unknown: the flow stops there (ADR-0070 §5).
  const [stoppedUnknown, setStoppedUnknown] = useState(false);
  const [instrumentId, setInstrumentId] = useState("");
  const [assessorId, setAssessorId] = useState("");
  // Held here rather than in step 3, so going back a step does not lose what was typed.
  const [studyName, setStudyName] = useState("");

  if (batchImport.roots.isLoading || batchImport.formats.isLoading) return <LoadingState />;
  const loadError = batchImport.roots.error ?? batchImport.formats.error;
  if (loadError) return <ErrorState message={(loadError as Error).message} />;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="space-y-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Evaluate courses</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Measure what one generator version produced. Three steps, and nothing is fixed
            until you start. Want every option on one page?{" "}
            <Link href="/admin/measure/all" className="text-primary hover:underline">
              Show all options
            </Link>
            .
          </p>
        </div>
        <Stepper step={step} />
      </div>

      {step === 1 ? (
        stoppedUnknown ? (
          <StoppedUnknown
            registered={batchImport.batch?.created ?? 0}
            onStartOver={() => {
              setStoppedUnknown(false);
              batchImport.setGenerator("");
              batchImport.invalidateScan();
            }}
          />
        ) : (
          <FolderStep
            batchImport={batchImport}
            onFormatChange={() => {
              // An instrument is chosen for a format; another format starts that choice over.
              setInstrumentId("");
              setAssessorId("");
            }}
            onContinue={() => {
              if (batchImport.declaredGenerator === null) setStoppedUnknown(true);
              else setStep(2);
            }}
          />
        )
      ) : null}

      {step === 2 && batchImport.declaredGenerator ? (
        <ThoroughStep
          format={batchImport.format}
          batch={batchImport.batch}
          instrumentId={instrumentId}
          assessorId={assessorId}
          onInstrument={(next, keepAssessor) => {
            setInstrumentId(next);
            if (!keepAssessor) setAssessorId("");
          }}
          onAssessor={setAssessorId}
          onBack={() => setStep(1)}
          onContinue={() => setStep(3)}
        />
      ) : null}

      {step === 3 && batchImport.declaredGenerator ? (
        <StartStep
          generatorVersionId={batchImport.declaredGenerator}
          instrumentId={instrumentId}
          assessorId={assessorId}
          name={studyName}
          onName={setStudyName}
          onBack={() => setStep(2)}
        />
      ) : null}
    </div>
  );
}

function Stepper({ step }: { step: Step }) {
  const steps = ["Folder", "How thorough", "Start"];
  return (
    <ol className="flex flex-wrap gap-2 text-xs">
      {steps.map((label, index) => {
        const number = (index + 1) as Step;
        const done = number < step;
        return (
          <li
            key={label}
            aria-current={number === step ? "step" : undefined}
            className={cn(
              "flex items-center gap-1 rounded-full border px-3 py-1",
              number === step && "border-primary font-medium text-primary",
              done && "border-emerald-600/40 bg-emerald-600/10 text-emerald-700 dark:text-emerald-400",
              number > step && "text-muted-foreground",
            )}
          >
            {done ? <Check className="h-3 w-3" /> : null}
            {number} · {label}
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------------- step 1

function FolderStep({
  batchImport,
  onFormatChange,
  onContinue,
}: {
  batchImport: ReturnType<typeof useImportBatch>;
  onFormatChange: () => void;
  onContinue: () => void;
}) {
  const {
    formats,
    roots,
    scanFolder,
    folder,
    format,
    setFormat,
    version,
    setVersion,
    editProvenance,
    setEditProvenance,
    root,
    setRoot,
    path,
    setPath,
    scan,
    outcomes,
    progress,
    setGenerator,
    generatorDeclared,
    declaredGenerator,
    invalidateScan,
    goTo,
    runScan,
    registerSelected,
  } = batchImport;

  const supported = formats.data ?? [];
  const mountBroken = scan?.result.mount_ok === false;
  const candidates = scan?.result.candidates ?? [];
  const registering = progress !== null;

  // Decided now, from the answer on screen, rather than from a selection made at scan time:
  // there are no checkboxes here to put back a row an earlier answer took out.
  const fresh = candidates.filter(
    (candidate) => REGISTRABLE.includes(candidate.verdict) && !outcomes[candidate.path],
  );
  const conflicting = fresh.filter(
    (candidate) =>
      declarationSignal(candidate, declaredGenerator, generatorDeclared) === "conflict",
  );
  const toRegister = fresh.filter((candidate) => !conflicting.includes(candidate));

  /** Other courses are another question: an answer about who made one folder is not an
   *  answer about the next, so it is asked again (ADR-0024). */
  function forgetGenerator() {
    setGenerator("");
  }

  function navigate(next: string) {
    goTo(next);
    forgetGenerator();
  }

  async function next() {
    if (toRegister.length > 0) await registerSelected(toRegister.map((c) => c.path));
    onContinue();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Which courses, and who made them</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {supported.length > 1 ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">What kind of courses are they?</legend>
            <div className="flex flex-wrap gap-2">
              {supported.map((name) => (
                <button
                  key={name}
                  type="button"
                  aria-pressed={format === name}
                  onClick={() => {
                    setFormat(name);
                    invalidateScan();
                    forgetGenerator();
                    onFormatChange();
                  }}
                  className={cn(
                    "rounded-md border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    format === name ? "border-primary bg-primary/5" : "hover:bg-accent/40",
                  )}
                >
                  <span className="block font-medium">{FORMAT_LABEL[name] ?? name}</span>
                  <span className="font-mono text-[11px] text-muted-foreground">{name}</span>
                </button>
              ))}
            </div>
          </fieldset>
        ) : null}

        <div className="space-y-2">
          <p className="text-sm font-medium">The folder that holds them</p>
          <p className="text-xs text-muted-foreground">
            Every folder inside the one you scan is one course.
          </p>
          <FolderBreadcrumb root={root} path={path} onNavigate={navigate} />
          {folder.isLoading ? (
            <LoadingState label="Reading the folder…" />
          ) : folder.error ? (
            <ErrorState message={(folder.error as Error).message} />
          ) : (folder.data?.entries.length ?? 0) === 0 ? (
            <p className="rounded-md border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">
              No folders here. If the courses are directly inside, scan this folder.
            </p>
          ) : (
            <ul className="grid gap-1 sm:grid-cols-2">
              {(folder.data?.entries ?? []).map((entry) => (
                <li key={entry.path}>
                  <button
                    type="button"
                    onClick={() => navigate(entry.path)}
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
          <Button
            variant={scan ? "outline" : "default"}
            onClick={runScan}
            disabled={!format || !root || scanFolder.isPending || registering}
          >
            {scanFolder.isPending ? <Spinner className="mr-2" /> : null}
            {scanFolder.isPending
              ? "Reading every package…"
              : scan
                ? "Scan again"
                : "Scan this folder"}
          </Button>
          {!format ? (
            <p className="text-xs text-muted-foreground">Say what kind of courses they are first.</p>
          ) : null}
        </div>

        {scan ? (
          <div className="space-y-4">
            {mountBroken ? (
              <ErrorState
                message={
                  scan.result.mount_detail ??
                  "The API does not serve this folder, so these courses cannot be registered."
                }
              />
            ) : null}
            {candidates.length === 0 ? (
              <EmptyState
                title="No courses in this folder"
                hint="Every course lives in its own folder. Go to the folder that holds them."
              />
            ) : (
              <>
                <ScanSummary candidates={candidates} />
                <GeneratorQuestion batchImport={batchImport} />
                <details className="text-sm">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                    Review each course
                  </summary>
                  <CandidateList candidates={candidates} />
                </details>
              </>
            )}
          </div>
        ) : null}

        <details className="rounded-md border px-3 py-2 text-sm">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            More options
          </summary>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="wizard-version">Course version</Label>
              <Input
                id="wizard-version"
                value={version}
                onChange={(event) => {
                  setVersion(event.target.value);
                  invalidateScan();
                  forgetGenerator();
                }}
              />
              <p className="text-xs text-muted-foreground">
                Raise it to register changed copies of courses already registered at this
                version.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wizard-provenance">Was it edited by a person?</Label>
              <Select
                id="wizard-provenance"
                value={editProvenance}
                onChange={(event) => setEditProvenance(event.target.value as EditProvenance)}
              >
                <option value="unknown">Don&apos;t know</option>
                <option value="pure">No, pure generator output</option>
                <option value="human_edited">Yes</option>
              </Select>
            </div>
            {(roots.data ?? []).length > 1 ? (
              <div className="space-y-1.5">
                <Label htmlFor="wizard-root">Source root</Label>
                <Select
                  id="wizard-root"
                  value={root}
                  onChange={(event) => {
                    setRoot(event.target.value);
                    setPath("");
                    invalidateScan();
                    forgetGenerator();
                  }}
                >
                  {(roots.data ?? []).map((source) => (
                    <option key={source.key} value={source.key} disabled={!source.exists}>
                      {source.key}
                      {source.exists ? "" : " (missing on disk)"}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}
          </div>
        </details>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t pt-4">
          {scan && !generatorDeclared ? (
            <p className="text-xs text-muted-foreground">
              Answer who made these courses to continue.
            </p>
          ) : null}
          {generatorDeclared && conflicting.length > 0 ? (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              {conflicting.length} {conflicting.length === 1 ? "course declares" : "courses declare"}{" "}
              another generator version and {conflicting.length === 1 ? "is" : "are"} skipped.
            </p>
          ) : null}
          <Button
            onClick={next}
            disabled={!scan || mountBroken || !generatorDeclared || registering}
          >
            {registering ? <Spinner className="mr-2" /> : null}
            {progress
              ? `Registering ${Math.min(progress.done + 1, progress.total)} of ${progress.total}…`
              : toRegister.length > 0
                ? `Register ${toRegister.length} ${toRegister.length === 1 ? "course" : "courses"} and continue`
                : "Continue"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ScanSummary({ candidates }: { candidates: ScanCandidate[] }) {
  const count = (verdicts: ScanVerdict[]) =>
    candidates.filter((candidate) => verdicts.includes(candidate.verdict)).length;
  const fresh = count(["new", "new_version"]);
  const known = count(["unchanged"]);
  const conflict = count(["conflict"]);
  const unreadable = count(["unreadable"]);
  return (
    <p className="rounded-md bg-muted/40 px-3 py-2 text-sm">
      <strong>
        {candidates.length} {candidates.length === 1 ? "folder" : "folders"}
      </strong>
      : {fresh} to register · {known} already registered
      {conflict ? ` · ${conflict} changed since registered (raise the course version under More options)` : ""}
      {unreadable ? ` · ${unreadable} not readable as a course` : ""}
    </p>
  );
}

/**
 * Who made these courses, asked once and answered explicitly (ADR-0024, ADR-0070 §2).
 *
 * When the packages agree on what they declare, the question is a confirmation; otherwise it
 * is the picker. Either way nothing is chosen until the reader clicks.
 */
function GeneratorQuestion({ batchImport }: { batchImport: ReturnType<typeof useImportBatch> }) {
  const { scan, generator, setGenerator, assistedRegister, setAssistedRegister } = batchImport;
  const generators = useGenerators();
  const [choosing, setChoosing] = useState(false);

  // The pairs the packages declare, deduplicated. One pair is a confirmation; none or several
  // are a question the reader answers with the picker.
  const declared = useMemo(() => {
    const pairs = new Map<string, ScanCandidate>();
    for (const candidate of scan?.result.candidates ?? []) {
      if (candidate.declared_generator_name && candidate.declared_generator_version) {
        pairs.set(
          `${candidate.declared_generator_name}\u0000${candidate.declared_generator_version}`,
          candidate,
        );
      }
    }
    return [...pairs.values()];
  }, [scan]);

  const single = declared.length === 1 ? declared[0] : null;
  const lineage = single
    ? (generators.data ?? []).find((g) =>
        looksLikeSameGeneratorName(g.name, single.declared_generator_name!),
      )
    : undefined;
  const confirmed =
    single !== null &&
    single.resolved_generator_version_id !== null &&
    generator === single.resolved_generator_version_id;

  const dialog = (
    <NewGeneratorVersionDialog
      open={assistedRegister !== null}
      generatorId={assistedRegister?.generatorId ?? ""}
      generatorName={assistedRegister?.generatorName ?? ""}
      initialVersion={assistedRegister?.version ?? ""}
      onClose={() => setAssistedRegister(null)}
      onCreated={(generatorVersionId) => {
        setGenerator(generatorVersionId);
        setAssistedRegister(null);
      }}
    />
  );

  if (!single || choosing) {
    return (
      <div className="space-y-2">
        <p className="flex items-center text-sm font-medium">
          Which generator version made these courses?
          <TermHint term="generator version" />
        </p>
        {declared.length > 1 ? (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            These packages declare different generator versions. A batch comes from one version:
            scan a folder that holds only that version&apos;s courses, or name it below.
          </p>
        ) : null}
        <GeneratorVersionPicker value={generator} onChange={setGenerator} />
        {generator === UNKNOWN_GENERATOR ? <UnknownNote /> : null}
        {dialog}
      </div>
    );
  }

  const name = `${single.declared_generator_name} ${single.declared_generator_version}`;
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">
        These courses say they come from <strong>{name}</strong>. Is that right?
      </p>
      <div className="flex flex-wrap gap-2">
        {single.resolved_generator_version_id ? (
          <Button
            variant={confirmed ? "default" : "outline"}
            size="sm"
            aria-pressed={confirmed}
            onClick={() => setGenerator(single.resolved_generator_version_id!)}
          >
            {confirmed ? <Check className="h-3.5 w-3.5" /> : null} Yes
          </Button>
        ) : lineage ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              setAssistedRegister({
                generatorId: lineage.generator_id,
                generatorName: single.declared_generator_name!,
                version: single.declared_generator_version!,
              })
            }
          >
            Yes, register {single.declared_generator_version}
          </Button>
        ) : null}
        <Button variant="outline" size="sm" onClick={() => setChoosing(true)}>
          No, choose another
        </Button>
        <Button
          variant={generator === UNKNOWN_GENERATOR ? "default" : "outline"}
          size="sm"
          aria-pressed={generator === UNKNOWN_GENERATOR}
          onClick={() => setGenerator(UNKNOWN_GENERATOR)}
        >
          Unknown
        </Button>
      </div>
      {!single.resolved_generator_version_id && lineage ? (
        <p className="text-xs text-muted-foreground">
          {single.declared_generator_version} is not registered yet. Registering it is its own
          act, and the button above does it.
        </p>
      ) : null}
      {!single.resolved_generator_version_id && !lineage ? (
        <p className="text-xs text-muted-foreground">
          No generator named &quot;{single.declared_generator_name}&quot; is registered.{" "}
          <Link href="/admin/generators" className="text-primary hover:underline">
            Register it
          </Link>{" "}
          first, or choose another.
        </p>
      ) : null}
      {generator === UNKNOWN_GENERATOR ? <UnknownNote /> : null}
      {dialog}
    </div>
  );
}

function UnknownNote() {
  return (
    <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
      Courses with an unknown generator can be registered, but this flow cannot measure them: it
      measures one named generator version, and such a study leaves them out. You can attribute
      a generator to them later, from Courses.
    </p>
  );
}

function StoppedUnknown({
  registered,
  onStartOver,
}: {
  registered: number;
  onStartOver: () => void;
}) {
  return (
    <Card>
      <CardContent className="space-y-3 pt-6 text-sm">
        <p className="font-medium">
          {registered > 0
            ? `${registered} ${registered === 1 ? "course is" : "courses are"} registered, with an unknown generator.`
            : "Nothing new was registered: these courses were already there."}
        </p>
        <p className="text-muted-foreground">
          A study measures named generator versions, so there is nothing to measure here yet.
          When you know which version made them, attribute it from{" "}
          <Link href="/admin/contents" className="text-primary hover:underline">
            Courses
          </Link>
          , and come back.
        </p>
        <Button variant="outline" onClick={onStartOver}>
          Start over
        </Button>
      </CardContent>
    </Card>
  );
}

function CandidateList({ candidates }: { candidates: ScanCandidate[] }) {
  return (
    <ul className="mt-2 divide-y rounded-md border">
      {candidates.map((candidate) => (
        <li key={candidate.path} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-3 py-2">
          <span className="font-medium">{candidate.title ?? candidate.name}</span>
          <span className="text-xs text-muted-foreground">{VERDICT_LABEL[candidate.verdict]}</span>
          {candidate.verdict === "unreadable" && candidate.error ? (
            <span className="w-full text-xs text-muted-foreground">{candidate.error}</span>
          ) : null}
          {candidate.verdict === "unchanged" && candidate.can_attribute_generator ? (
            <span className="w-full text-xs text-amber-700 dark:text-amber-400">
              Registered before with no generator. Attribute one from the long view (Show all
              options).
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------------- step 2

function ThoroughStep({
  format,
  batch,
  instrumentId,
  assessorId,
  onInstrument,
  onAssessor,
  onBack,
  onContinue,
}: {
  format: string;
  /** What registering just did, if anything: whether the lot came back readable is the
   *  first thing to know before measuring it. */
  batch: ReturnType<typeof useImportBatch>["batch"];
  instrumentId: string;
  assessorId: string;
  /** `keepAssessor` is true when the chosen assessor has also ratified the new instrument. */
  onInstrument: (instrumentId: string, keepAssessor: boolean) => void;
  onAssessor: (assessorId: string) => void;
  onBack: () => void;
  onContinue: () => void;
}) {
  const instruments = useInstruments();
  const packages = useAssessorPackages();
  const matchings = useMatchings(instrumentId || null, format ? [format] : []);

  if (instruments.isLoading || packages.isLoading) return <LoadingState />;
  const loadError = instruments.error ?? packages.error;
  if (loadError) return <ErrorState message={(loadError as Error).message} />;

  const readable = (instruments.data ?? []).filter(
    (instrument) =>
      instrument.status === "published" &&
      instrument.bindings.some((binding) => binding.package_format === format),
  );
  // A choice made for another format does not carry over: it counts only if it is offered.
  const chosen = readable.some((i) => i.instrument_version_id === instrumentId)
    ? instrumentId
    : "";
  const eligible = ratifiedFor(packages.data ?? [], chosen);

  return (
    <Card>
      <CardHeader>
        <CardTitle>How thorough</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <BatchSummary batch={batch} format={format} />
        <InstrumentChoice
          instruments={readable}
          value={chosen}
          onChange={(next) =>
            onInstrument(
              next,
              ratifiedFor(packages.data ?? [], next).some((pkg) => pkg.assessor_id === assessorId),
            )
          }
        />
        {chosen ? (
          <AssessorChoice
            assessors={eligible}
            matching={matchings.byFormat.get(format)}
            format={format}
            value={assessorId}
            onChange={onAssessor}
          />
        ) : null}
        <p className="text-xs text-muted-foreground">
          Not sure what the difference is?{" "}
          <Link href="/admin/how-it-works" className="text-primary hover:underline">
            How evaluation works
          </Link>{" "}
          explains how an assessor decides a criterion.
        </p>
        <div className="flex flex-wrap justify-between gap-3 border-t pt-4">
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
          <Button
            onClick={onContinue}
            disabled={!chosen || !eligible.some((pkg) => pkg.assessor_id === assessorId)}
          >
            Continue
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------------- step 3

function StartStep({
  generatorVersionId,
  instrumentId,
  assessorId,
  name,
  onName: setName,
  onBack,
}: {
  generatorVersionId: Uuid;
  instrumentId: string;
  assessorId: string;
  name: string;
  onName: (name: string) => void;
  onBack: () => void;
}) {
  const contents = useContents();
  const generatorVersions = useGeneratorVersions();
  const packages = useAssessorPackages();
  const instruments = useInstruments();
  const { saveDraft, saveAndEvaluate, busy } = useSaveAndStart();
  const [confirming, setConfirming] = useState(false);

  const version = (generatorVersions.data ?? []).find(
    (candidate) => candidate.generator_version_id === generatorVersionId,
  );
  // Named after the version once it is known, unless somebody has typed a name already.
  useEffect(() => {
    if (version && !name) setName(`${version.name} ${version.version}`);
  }, [version, name, setName]);

  if (contents.data === undefined || generatorVersions.data === undefined) {
    return <LoadingState label="Reading what this version made…" />;
  }

  const group = groupByVersion(contents.data, generatorVersions.data).find(
    (candidate) => candidate.key === generatorVersionId,
  );
  const assessor = (packages.data ?? []).find((pkg) => pkg.assessor_id === assessorId);
  const instrument = (instruments.data ?? []).find(
    (candidate) => candidate.instrument_version_id === instrumentId,
  );
  const briefIds = [...(group?.briefIds ?? [])];
  const courses = (group?.courses ?? []).filter((course) => course.brief_id !== null).length;
  const calls = assessor?.uses_llm ? courses * assessor.executes.length : 0;
  // The study takes every course of the version, in whatever format; the instrument was
  // chosen for one. Courses in a format it does not read come back not applicable.
  const unread = (group?.courses ?? []).filter(
    (course) =>
      course.brief_id !== null &&
      !(instrument?.bindings ?? []).some((b) => b.package_format === course.package_format),
  );
  const unreadFormats = [...new Set(unread.map((course) => course.package_format))];
  const label = version ? `${version.name} ${version.version}` : "this version";

  const body = {
    name: name.trim(),
    description: null,
    instrument_version_id: instrumentId,
    assessor_id: assessorId as Uuid,
    brief_ids: briefIds,
    generator_scope: [generatorVersionId],
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Start</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="wizard-name">Name</Label>
          <Input
            id="wizard-name"
            className="max-w-md"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Names the study for whoever reads its report later.
          </p>
        </div>

        <dl className="grid gap-x-6 gap-y-2 rounded-md border p-4 text-sm sm:grid-cols-[10rem_1fr]">
          <dt className="text-muted-foreground">Courses</dt>
          <dd>
            {courses} {courses === 1 ? "course" : "courses"} of {label}, from {briefIds.length}{" "}
            {briefIds.length === 1 ? "brief" : "briefs"}
            {group && group.withoutBrief > 0 ? (
              <span className="block text-xs text-amber-700 dark:text-amber-400">
                {group.withoutBrief} {group.withoutBrief === 1 ? "course has" : "courses have"} no
                brief, so {group.withoutBrief === 1 ? "it stays" : "they stay"} out.
              </span>
            ) : null}
            <span className="block text-xs text-muted-foreground">
              Every registered course of this version, not only the ones you just imported.
            </span>
          </dd>
          <dt className="text-muted-foreground">Instrument</dt>
          <dd>{instrument?.name ?? instrumentId}</dd>
          <dt className="text-muted-foreground">Assessor</dt>
          <dd>{assessor?.display_name ?? assessorId}</dd>
          <dt className="text-muted-foreground">Cost</dt>
          <dd>
            {calls > 0
              ? `About ${calls} model calls, spent on the backend's key`
              : "No model calls"}
          </dd>
        </dl>

        {unread.length > 0 ? (
          <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-sm text-muted-foreground">
            {unread.length} of these courses {unread.length === 1 ? "is" : "are"} in{" "}
            {unreadFormats.join(", ")}, which this instrument does not read. Their criteria
            will come back not applicable. The study still runs; the report will say so.
          </p>
        ) : null}

        {courses === 0 ? (
          <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-sm text-muted-foreground">
            No course of {label} has a brief, so there is nothing a study can measure.
          </p>
        ) : null}

        <div className="flex flex-wrap justify-between gap-3 border-t pt-4">
          <Button variant="ghost" onClick={onBack} disabled={busy}>
            Back
          </Button>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => saveDraft(body)}
              disabled={busy || !name.trim() || courses === 0}
            >
              Save as draft
            </Button>
            <Button
              onClick={() => setConfirming(true)}
              disabled={busy || !name.trim() || courses === 0}
            >
              Start the study
            </Button>
          </div>
        </div>
      </CardContent>

      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title={`Start “${name.trim()}”?`}
        description="This does two things at once, and neither can be undone."
      >
        <ul className="space-y-2 text-sm">
          <li className="rounded border p-2">
            <span className="font-medium">The instrument, the assessor and these courses are fixed</span>
            <span className="mt-1 block text-xs text-muted-foreground">
              That is what keeps the result comparable. Changing any of them afterwards means a
              new study.
            </span>
          </li>
          <li className="rounded border p-2">
            <span className="font-medium">
              {courses} {courses === 1 ? "course" : "courses"} evaluated now
              {calls > 0 ? `, about ${calls} model calls` : ", no model calls"}
            </span>
            <span className="mt-1 block text-xs text-muted-foreground">
              It reports as it goes and can be stopped at any time. What finished stays
              evaluated.
            </span>
          </li>
        </ul>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setConfirming(false)} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={() => saveAndEvaluate(body, () => setConfirming(false))}
            disabled={busy}
          >
            {busy ? <Spinner /> : null} Start
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}
