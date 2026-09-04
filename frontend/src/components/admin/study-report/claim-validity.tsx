"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Select } from "@/components/ui/select";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { ValidityBadge } from "@/components/admin/study-report/validity-badge";
import { useCampaigns, useGoldenStatus } from "@/lib/api/hooks";
import type { ClaimValidity, ClaimValidityReport, Uuid } from "@/lib/api/types";

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
              <tr key={claim.claim_id} className="align-top">
                <td className="px-3 py-2">
                  <span className="block" title={claim.claim_id}>
                    {claim.statement}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {claim.quality_id}
                    {claim.grey > 0 ? ` · ${claim.grey} in the grey zone` : ""}
                  </span>
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
