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
import { ValidityBadge } from "@/components/admin/validity-badge";
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
  useCampaigns,
  useClaimValidity,
  useContents,
  useGoldenStatus,
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
  CampaignResponse,
  ClaimValidity,
  ClaimValidityReport,
  GoldenStatus,
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
  // The fourth coordinate, and the only one that is not part of the run (ADR-0064). It is
  // read from the URL the same way, because the validity table links here with the campaign
  // its numbers came from and choosing it twice is a chore, not a choice.
  const [campaignId, setCampaignId] = useState<Uuid | "">(
    () => (params.get("campaign") as Uuid | null) ?? "",
  );
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

  // What a panel of experts made of the claims this instrument asserts (ADR-0064). The three
  // coordinates ADR-0063 §7 demands are all explicit: two of them are the run's own choices,
  // and the campaign is the one asked for here. The hook stays disabled until all three
  // resolve, so a package with no identity row simply never fires it.
  const campaigns = useCampaigns();
  const golden = useGoldenStatus(campaignId || "");
  const validity = useClaimValidity(
    campaignId || null,
    selectedPackage?.assessor_id ?? null,
    instrumentVersionId || null,
  );
  // Ratification is what says this pair could ever have judged anything. The dry run needs
  // none of it (that is the point of this page), so a package can be perfectly runnable here
  // and have nothing measured about it — two different states, said apart (ADR-0064 §5).
  const ratifiedHere = selectedPackage?.lineage_versions.some(
    (v) => v.instrument_version_id === instrumentVersionId && v.ratified,
  );

  const validityByClaim = useMemo(
    () =>
      new Map<string, ClaimValidity>((validity.data?.claims ?? []).map((c) => [c.claim_id, c])),
    [validity.data],
  );
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
        cameFromValidity={params.get("why") === "validity"}
        criterion={selectedInstrument?.criteria.find((c) => c.criterion_id === cameAbout)}
        criterionId={cameAbout}
        unprofiled={Boolean(contentId) && profileStatus.get(contentId as Uuid) !== "ok"}
        // A criterion has no human number of its own; it reaches one through the claims it
        // evidences (ADR-0064 §1). Several claims means several readings, never an average.
        claimValidity={(
          selectedInstrument?.criteria.find((c) => c.criterion_id === cameAbout)?.claim_ids ?? []
        )
          .map((claimId) => validityByClaim.get(claimId))
          .filter((found): found is ClaimValidity => found !== undefined)}
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
              <p className="text-xs text-amber-700 dark:text-amber-400">
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

      <AgainstThePanel
        campaignId={campaignId}
        onCampaignChange={setCampaignId}
        campaigns={campaigns.data ?? []}
        golden={golden.data}
        assessorId={selectedPackage?.assessor_id ?? null}
        packageName={selectedPackage?.display_name ?? null}
        ratified={ratifiedHere}
        instrument={selectedInstrument}
        report={validity.data}
        loading={validity.isLoading}
        validityByClaim={validityByClaim}
      />

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
                  validityByClaim={validityByClaim}
                />
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

/** What a panel of experts made of the claims this instrument asserts (ADR-0064).
 *
 *  Everything else on this page measures whether the instrument is **reliable** — traces,
 *  repeats, self-agreement. All of it is internal to the machine, and the runbook says why
 *  that is not enough: a criterion can be perfectly stable and stably wrong, and no number of
 *  runs would show it. This is the only external evidence there is.
 *
 *  Outside the numbered steps on purpose: it is not part of the run, it changes nothing about
 *  one, and a reader who has no campaign can ignore it entirely. */
function AgainstThePanel({
  campaignId,
  onCampaignChange,
  campaigns,
  golden,
  assessorId,
  packageName,
  ratified,
  instrument,
  report,
  loading,
  validityByClaim,
}: {
  campaignId: Uuid | "";
  onCampaignChange: (campaign: Uuid | "") => void;
  campaigns: CampaignResponse[];
  golden: GoldenStatus | undefined;
  assessorId: Uuid | null;
  packageName: string | null;
  ratified: boolean | undefined;
  instrument: InstrumentResponse | undefined;
  report: ClaimValidityReport | undefined;
  loading: boolean;
  validityByClaim: Map<string, ClaimValidity>;
}) {
  // Only a campaign that has been opened can have judged anything.
  const options = campaigns.filter((option) => option.status !== "draft");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Against a panel of experts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Everything else on this page tells you whether the instrument is{" "}
          <strong>reliable</strong> — whether it says the same thing twice. Only a panel that
          read the same courses tells you whether it is <strong>valid</strong>, and a check can
          be perfectly stable and stably wrong.
        </p>

        <div className="max-w-md space-y-1.5">
          <Label htmlFor="calibration-campaign">Campaign</Label>
          <Select
            id="calibration-campaign"
            value={campaignId}
            onChange={(event) => onCampaignChange(event.target.value as Uuid | "")}
          >
            <option value="">No campaign — nothing is qualified</option>
            {options.map((option) => (
              <option key={option.campaign_id} value={option.campaign_id}>
                {option.name}
              </option>
            ))}
          </Select>
        </div>

        {campaignId && golden && !golden.usable ? (
          <p className="rounded-md border border-dashed bg-muted/30 p-3 text-xs text-muted-foreground">
            This campaign has not reached its coverage threshold yet (
            {Math.round(golden.coverage * 100)}% of {Math.round(golden.threshold * 100)}%), so
            its answers are still arriving. What is below will change.
          </p>
        ) : null}

        <PanelReading
          campaignId={campaignId}
          assessorId={assessorId}
          packageName={packageName}
          ratified={ratified}
          instrument={instrument}
          report={report}
          loading={loading}
          validityByClaim={validityByClaim}
        />
      </CardContent>
    </Card>
  );
}

/** One state at a time, each saying its own reason.
 *
 *  *Nobody measured this* and *we measured it and it does not conclude* are different facts
 *  (ADR-0011 §3), and so are the three ways the first one happens: the package has no identity
 *  yet, it was never allowed to judge with this version, or it judged none of these courses.
 *  One blank table for all of them would hide which. */
function PanelReading({
  campaignId,
  assessorId,
  packageName,
  ratified,
  instrument,
  report,
  loading,
  validityByClaim,
}: {
  campaignId: Uuid | "";
  assessorId: Uuid | null;
  packageName: string | null;
  ratified: boolean | undefined;
  instrument: InstrumentResponse | undefined;
  report: ClaimValidityReport | undefined;
  loading: boolean;
  validityByClaim: Map<string, ClaimValidity>;
}) {
  if (!campaignId) {
    return (
      <p className="text-sm text-muted-foreground">
        Choose a campaign to see how far these claims agree with its panel. With none chosen
        nothing is shown, which is not the same as a claim that failed to measure.
      </p>
    );
  }

  if (!instrument) {
    return <p className="text-sm text-muted-foreground">Pick an instrument version first.</p>;
  }

  if (assessorId === null) {
    return (
      <Note>
        {packageName ? <strong>{packageName}</strong> : "This assessor"} has never been
        ratified, so it has no identity of its own yet and nothing has been measured about it.
        The first ratification mints it. A dry run needs none of that and still works.
      </Note>
    );
  }

  if (ratified === false) {
    return (
      <Note>
        This assessor was never ratified against{" "}
        <span className="font-mono text-xs">{instrument.instrument_version_id}</span>, so it
        cannot have judged anything with it and there is nothing to compare. Dry-running it
        here is how that gets decided — ratification stays a separate, human act.
      </Note>
    );
  }

  if (loading) return <LoadingState label="Crossing the two sides…" />;
  if (!report) return null;

  if (report.courses_judged === 0) {
    return (
      <Note>
        This assessor has judged none of{" "}
        <span className="font-medium text-foreground">{report.campaign_name}</span>&apos;s
        courses with this version. The comparison needs both sides over the same courses: run a
        study over the dataset that campaign was opened on, and come back.
      </Note>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {report.courses_judged} of {report.courses_in_campaign} courses in{" "}
        <span className="font-medium text-foreground">{report.campaign_name}</span> were judged
        by both sides. Hover a badge for the counts behind it.
      </p>
      <ul className="space-y-1.5">
        {/* From the instrument, never from a run: a claim excluded by coverage has no row in a
            judgment at all, and would vanish here without a trace (ADR-0064 §2). */}
        {instrument.claims.map((claim) => (
          <li key={claim.claim_id} className="flex flex-wrap items-baseline gap-2 text-sm">
            <ValidityBadge validity={validityByClaim.get(claim.claim_id)} />
            <span title={claim.claim_id}>{claim.statement}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        This qualifies the claim, not this page&apos;s run: a dry run persists nothing and
        changes none of it. And it is one campaign&apos;s reading — another one is asked for by
        name, never averaged with this.
      </p>
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-dashed bg-muted/30 p-3 text-sm text-muted-foreground">
      {children}
    </p>
  );
}

/** Why the reader is here, when a study report sent them.
 *
 *  Arriving with the course and the instrument already chosen is most of the value; naming
 *  what the criterion demands is the rest. The question they came with is whether the check
 *  is wrong, and reading its pass condition often answers it before anything is run.
 *
 *  Two reports send people here and they arrive with different questions. From the criteria
 *  rollup the course failed a check. From the validity table nothing failed: a panel of
 *  experts read the course the other way round, and where the assessor was the one that said
 *  `supported` there is no failure to speak of at all. Saying "that course failed" there
 *  would be false about the very case that brought them. */
function ArrivedFromReport({
  preselected,
  cameFromValidity,
  criterion,
  criterionId,
  unprofiled,
  claimValidity,
}: {
  preselected: boolean;
  cameFromValidity: boolean;
  criterion: InstrumentCriterion | undefined;
  criterionId: string | null;
  unprofiled: boolean;
  /** The claims this criterion evidences, where a campaign has qualified them. */
  claimValidity: ClaimValidity[];
}) {
  if (!preselected) return null;

  const named = criterion ? (
    <em>{criterion.statement ?? criterion.criterion_id}</em>
  ) : criterionId ? (
    <code>{criterionId}</code>
  ) : null;

  return (
    <div className="space-y-1 rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm">
      {cameFromValidity ? (
        <p>
          <strong>Preselected from a claim&apos;s validity.</strong> A panel of experts read
          this course the other way round from the assessor
          {named ? <>, over {named}</> : null} under this instrument version. Pick an assessor
          and run it: a dry run persists nothing, so this is the safe place to find out whether
          the check asks the wrong thing or the judge reads it badly. Start with the check —
          a threshold nobody wrote makes every assessor look equally bad.
        </p>
      ) : (
        <p>
          <strong>Preselected from a study report.</strong> That course failed{" "}
          {named ?? "a criterion"} under this instrument version. Pick an assessor and run it:
          a dry run persists nothing, so this is the safe place to find out whether the
          criterion is wrong or the course is.
        </p>
      )}
      {criterion ? (
        <p className="text-xs text-muted-foreground">
          It passes when: {criterion.pass_condition}
        </p>
      ) : null}
      {claimValidity.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>What the panel made of the claims it evidences:</span>
          {claimValidity.map((validity) => (
            <span key={validity.claim_id} className="inline-flex items-center gap-1">
              <ValidityBadge validity={validity} />
              <span title={validity.claim_id}>{validity.quality_id}</span>
            </span>
          ))}
        </div>
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
  validityByClaim,
}: {
  result: PreviewEvaluationResponse;
  instrument: InstrumentResponse;
  qualityReference: QualityReferenceResponse[];
  /** The criterion a study report sent the reader here about: its row is marked, so they
   *  land on the answer instead of scanning thirty of them. */
  focusCriterionId?: string | null;
  /** Empty until a campaign is chosen above. What it adds is the contrast: this run says
   *  what the claim came out as, the badge says how much that verdict has been worth. */
  validityByClaim: Map<string, ClaimValidity>;
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
          <h3 className="mb-1 text-sm font-medium">Claims</h3>
          {/* Two badges, two different things, and they sit on one line: the first is what
              this run concluded, the second is what a panel made of that claim before any of
              this. A dry run cannot move the second one (ADR-0064 §4). */}
          <p className="mb-2 text-xs text-muted-foreground">
            The first badge is this run&apos;s verdict. The second, where a campaign is chosen
            above, is how much that claim has been worth against experts — it is about the
            published pair, not about this run.
          </p>
          <ul className="space-y-1.5">
            {result.claims.map((claim) => (
              <li key={claim.claim_id} className="flex flex-wrap items-center gap-2 text-xs">
                <ClaimStatusBadge status={claim.status} />
                <ValidityBadge validity={validityByClaim.get(claim.claim_id)} />
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
