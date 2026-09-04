"use client";

import { useState } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Select } from "@/components/ui/select";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { EvidenceQuote } from "@/components/admin/evidence-quote";
import { ValidityBadge } from "@/components/admin/study-report/validity-badge";
import { useCampaigns, useGoldenStatus } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import type {
  ClaimValidity,
  ClaimValidityReport,
  DiscordantCourse,
  Uuid,
} from "@/lib/api/types";

/** How much this study's assessor follows a panel of experts, claim by claim (ADR-0063).
 *
 *  The study already pins the assessor and the instrument version, so the only coordinate left
 *  to choose is the campaign — and choosing it is the point, not a convenience. Two campaigns
 *  are read one at a time and never averaged: if they disagree, that IS the finding.
 *
 *  With no campaign chosen there is nothing here, deliberately. *Nobody measured this* and *we
 *  measured it and it does not conclude* are different facts, and only the second is
 *  `unvalidated`.
 *
 *  Controlled from the report root, which owns the choice because the badge on the claims
 *  above answers to the same one. */
export function ClaimValiditySection({
  campaign,
  onCampaignChange,
  validity,
  pinned,
}: {
  campaign: Uuid | "";
  onCampaignChange: (campaign: Uuid | "") => void;
  validity: UseQueryResult<ClaimValidityReport>;
  /** False while the study has not pinned an assessor and an instrument version. */
  pinned: boolean;
}) {
  const campaigns = useCampaigns();
  const golden = useGoldenStatus(campaign || "");

  if (!pinned) {
    return (
      <CollapsibleSection title="Validity" defaultOpen={false}>
        <p className="text-sm text-muted-foreground">
          This study has not pinned an assessor and an instrument version yet, so there is no
          pair to qualify.
        </p>
      </CollapsibleSection>
    );
  }

  // Only a campaign that has been opened can have judged anything.
  const options = (campaigns.data ?? []).filter((option) => option.status !== "draft");

  return (
    <CollapsibleSection
      title="Validity"
      badge={
        validity.data && validity.data.courses_judged > 0 ? (
          <Badge variant="outline">{validity.data.courses_judged} courses compared</Badge>
        ) : null
      }
      defaultOpen={false}
    >
      <div className="space-y-4">
        <p className="max-w-2xl text-sm text-muted-foreground">
          Against a campaign of experts, how much each claim of this study&apos;s assessor
          follows human judgment. It qualifies the verdicts above — it never changes them.
        </p>
        <p className="max-w-2xl text-xs text-muted-foreground">
          The comparison runs over <span className="font-medium">the campaign&apos;s courses</span>,
          wherever this assessor judged them — not over this study&apos;s dataset. Validity is a
          property of the assessor and its instrument, so one run qualifies every study that
          pins the same pair.
        </p>

        <div className="flex max-w-md flex-col gap-1.5">
          <label htmlFor="validity-campaign" className="text-xs font-medium">
            Campaign
          </label>
          <Select
            id="validity-campaign"
            value={campaign}
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

        {campaign && golden.data && !golden.data.usable ? (
          <p className="rounded-md border border-dashed bg-muted/30 p-3 text-xs text-muted-foreground">
            This campaign has not reached its coverage threshold yet (
            {Math.round(golden.data.coverage * 100)}% of{" "}
            {Math.round(golden.data.threshold * 100)}%), so its answers are still arriving.
            What is below will change.
          </p>
        ) : null}

        {!campaign ? (
          <p className="text-sm text-muted-foreground">
            Choose a campaign to see how far these claims agree with its panel.
          </p>
        ) : validity.isLoading ? (
          <LoadingState label="Crossing the two sides…" />
        ) : validity.error ? (
          <ErrorState message={(validity.error as Error).message} />
        ) : validity.data ? (
          <ValidityTable report={validity.data} />
        ) : null}
      </div>
    </CollapsibleSection>
  );
}

function ValidityTable({ report }: { report: ClaimValidityReport }) {
  // Nothing to read is not the same as nothing to say. Twenty-one `unvalidated` rows look
  // like a verdict on the claims; what actually happened is that the run nobody made yet
  // has not been made.
  if (report.courses_judged === 0) {
    return (
      <div className="rounded-md border border-dashed bg-muted/30 p-4 text-sm">
        <p className="font-medium">
          This assessor has not judged any of this campaign&apos;s courses.
        </p>
        <p className="mt-1.5 text-muted-foreground">
          The comparison needs both sides over the same courses. Run{" "}
          <span className="font-medium text-foreground">{report.assessor_name ?? "this assessor"}</span>{" "}
          with{" "}
          <span className="font-medium text-foreground">{report.instrument_name}</span> over the
          dataset <span className="font-medium text-foreground">{report.campaign_name}</span> was
          opened on, and come back. It is one run, and it qualifies every study that pins this
          pair.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {report.courses_judged} of {report.courses_in_campaign} courses in the campaign have
        also been judged by this assessor, in whichever study did it. Every number below reads
        against that overlap.
      </p>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full min-w-[46rem] text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
              <th className="px-3 py-2 font-medium">Claim</th>
              <th className="px-3 py-2 font-medium">Of accepted</th>
              <th className="px-3 py-2 font-medium">Of rejected</th>
              <th className="px-3 py-2 font-medium">κ</th>
              <th className="px-3 py-2 font-medium">Experts agree</th>
              <th className="px-3 py-2 font-medium">Reading</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {report.claims.map((claim) => (
              <ClaimRow key={claim.claim_id} claim={claim} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Experts agree</span> is the ceiling: the
        assessor cannot match a panel that does not match itself. A claim near it is as good as
        this campaign can show.
      </p>
    </div>
  );
}

/** One claim, and — folded under it — the courses that contradicted its assessor.
 *
 *  The numbers say how much the claim follows the panel; only the courses say why, and why is
 *  what a rewrite is made of. Deliberately not gated on `weak`: a claim left `unvalidated` for
 *  want of courses still has disagreements worth reading, and on a short campaign that is the
 *  only thing there is to read. */
function ClaimRow({ claim }: { claim: ClaimValidity }) {
  const [open, setOpen] = useState(false);
  const courses = claim.discordant;
  const disclosable = courses.length > 0;

  return (
    <>
      <tr className="align-top">
        <td className="px-3 py-2">
          {disclosable ? (
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              className="flex w-full items-start gap-1.5 text-left hover:text-foreground/80"
            >
              <ChevronDown
                className={cn(
                  "mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
                  !open && "-rotate-90",
                )}
              />
              <span className="min-w-0">
                <span className="block" title={claim.claim_id}>
                  {claim.statement}
                </span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  <Coordinates claim={claim} /> ·{" "}
                  <span className="font-medium text-foreground">
                    {courses.length} disagreed
                  </span>
                </span>
              </span>
            </button>
          ) : (
            <>
              <span className="block" title={claim.claim_id}>
                {claim.statement}
              </span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                <Coordinates claim={claim} />
              </span>
            </>
          )}
        </td>
        <td className="px-3 py-2 tabular-nums">
          <Count ratio={claim.sensitivity} />
        </td>
        <td className="px-3 py-2 tabular-nums">
          <Count ratio={claim.specificity} />
        </td>
        <td className="px-3 py-2 tabular-nums">
          <Coefficient value={claim.kappa} />
        </td>
        <td className="px-3 py-2 tabular-nums">
          <Coefficient value={claim.human_agreement} percent />
        </td>
        <td className="px-3 py-2">
          <ValidityBadge validity={claim} />
        </td>
      </tr>
      {open && disclosable ? (
        <tr>
          <td colSpan={6} className="bg-muted/20 px-3 py-3">
            <p className="mb-3 max-w-2xl text-xs text-muted-foreground">
              Where the two sides read the same course differently, widest disagreement first.
              Both readings are shown as they were given: nothing here corrects a course, and
              neither side is the one that was right.
            </p>
            <ul className="space-y-3">
              {courses.map((course) => (
                <DiscordantEntry key={course.content_id} course={course} />
              ))}
            </ul>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function Coordinates({ claim }: { claim: ClaimValidity }) {
  return (
    <>
      {claim.quality_id}
      {claim.grey > 0 ? ` · ${claim.grey} in the grey zone` : ""}
    </>
  );
}

/** One course, read in the order the diagnosis has to be read.
 *
 *  The panel's own agreement comes first because it decides whether anything below it means
 *  anything: where two experts read the same course differently there is no human answer for
 *  the assessor to have matched, and the suspect is the item, not the judge. */
function DiscordantEntry({ course }: { course: DiscordantCourse }) {
  const refutedWhatWasAccepted = course.cell === "refuted_accepted";

  return (
    <li className="rounded-md border bg-background p-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-medium">{course.title ?? course.external_id}</span>
        <span className="font-mono text-xs text-muted-foreground">{course.external_id}</span>
      </div>

      <p className="mt-1 text-xs">
        {refutedWhatWasAccepted ? (
          <>
            The experts <span className="font-medium text-foreground">accepted</span> it (mean{" "}
            {course.human_mean.toFixed(1)}) and the assessor{" "}
            <span className="font-medium text-foreground">refuted</span> the claim.
          </>
        ) : (
          <>
            The experts <span className="font-medium text-foreground">rejected</span> it (mean{" "}
            {course.human_mean.toFixed(1)}) and the assessor{" "}
            <span className="font-medium text-foreground">supported</span> the claim.
          </>
        )}
      </p>

      {course.experts_agree === false ? (
        <p className="mt-2 rounded border border-dashed bg-muted/30 px-2 py-1.5 text-xs text-muted-foreground">
          The experts did not agree with each other on this course, so there is no human answer
          here for the assessor to have matched. Read the item before reading the judge.
        </p>
      ) : null}

      <ul className="mt-2 space-y-1.5">
        {course.answers.map((answer) => (
          <li key={answer.assessor_id} className="text-xs">
            <span className="tabular-nums font-medium">{answer.score}</span>
            <span className="text-muted-foreground"> · {answer.assessor_name ?? "an expert"}</span>
            {answer.comment ? (
              <span className="mt-0.5 block whitespace-pre-wrap text-muted-foreground">
                {answer.comment}
              </span>
            ) : null}
          </li>
        ))}
      </ul>

      <div className="mt-3 border-t pt-2">
        {course.findings.length > 0 ? (
          <ul className="space-y-2">
            {course.findings.map((finding, index) => (
              <li key={`${finding.criterion_id}-${index}`} className="space-y-1">
                <p className="text-xs text-muted-foreground">
                  <span className="font-mono">{finding.criterion_id}</span> ·{" "}
                  {finding.failure_mode}
                </p>
                <EvidenceQuote
                  quote={finding.quote}
                  locator={finding.locator}
                  absentCause="the absence IS the finding"
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">
            The assessor raised nothing here — that silence is what the experts contradicted.
            It concluded from <EvidenceBasis basis={course.evidence_basis} />.
          </p>
        )}
      </div>
    </li>
  );
}

/** What the claim was concluded from, spelled out. An empty basis says the criteria behind
 *  this claim were never recorded, which is a different fact from all of them passing. */
function EvidenceBasis({ basis }: { basis: Record<string, number> }) {
  const parts = Object.entries(basis).filter(([, count]) => count > 0);
  if (parts.length === 0) return <span>criteria it did not record</span>;
  return <span>{parts.map(([state, count]) => `${count} ${state}`).join(", ")}</span>;
}

/** A proportion with its denominator, because `82 %` over 11 courses and over 400 are not the
 *  same assertion. Nothing measured shows nothing — never `0 / 0` dressed as a score. */
function Count({ ratio }: { ratio: ClaimValidity["sensitivity"] }) {
  if (ratio.of === 0) return <Nothing />;
  return (
    <span>
      {ratio.hit} of {ratio.of}
    </span>
  );
}

/** Null is not zero — the house rule `FitnessValue` follows, for the same reason: a
 *  coefficient the table cannot support is undefined, and 0 would be a verdict nobody reached. */
function Coefficient({ value, percent = false }: { value: number | null; percent?: boolean }) {
  if (value === null) return <Nothing />;
  return <span>{percent ? `${Math.round(value * 100)}%` : value.toFixed(2)}</span>;
}

function Nothing() {
  return <span className="italic text-muted-foreground">—</span>;
}
