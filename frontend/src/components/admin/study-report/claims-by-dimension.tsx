"use client";

import { CopyButton } from "@/components/ui/copy-button";
import { DistributionBar } from "@/components/admin/distribution-bar";
import { ValidityBadge } from "@/components/admin/validity-badge";
import type {
  ClaimValidity,
  InstrumentResponse,
  QualityReferenceResponse,
  ReportBody,
  StudyReportGeneratorClaim,
} from "@/lib/api/types";

/**
 * What the study found, claim by claim, grouped the way a reader thinks about a course:
 * dimension, then quality, then the claims about it.
 *
 * Two sources and one rule each:
 *
 * - **Where a quality belongs** is the map the instrument version froze at publish
 *   (ADR-0023 §8), never the live vocabulary, so a later edit of the vocabulary cannot move
 *   a published study's claims between dimensions.
 * - **What to call it** is the live vocabulary, which is only names.
 *
 * And one thing it never does: add anything up. Each claim keeps its own distribution and
 * its own coverage, and a dimension says how many claims it holds, not how well it did
 * (ADR-0011, ADR-0041 §5).
 */
type Row = {
  claimId: string;
  statement: string;
  qualityId: string | null;
  /** One entry per generator version the study measured, in the report's order. */
  readings: { label: string; claim: StudyReportGeneratorClaim | null }[];
};

type Group = {
  dimensionId: string | null;
  qualities: { qualityId: string | null; rows: Row[] }[];
};

function generatorLabel(generator: ReportBody["generatorLevel"][number]): string {
  return generator.name
    ? `${generator.name}${generator.version ? ` ${generator.version}` : ""}`
    : generator.generatorVersionId;
}

function groupClaims(body: ReportBody, instrument: InstrumentResponse): Group[] {
  const groups: Group[] = [];
  for (const claim of instrument.claims) {
    const qualityId = claim.quality_ids[0] ?? null;
    const dimensionId = qualityId ? (instrument.quality_dimensions[qualityId] ?? null) : null;
    const row: Row = {
      claimId: claim.claim_id,
      statement: claim.statement,
      qualityId,
      readings: body.generatorLevel.map((generator) => ({
        label: generatorLabel(generator),
        claim: generator.perClaim.find((c) => c.claimId === claim.claim_id) ?? null,
      })),
    };
    let group = groups.find((g) => g.dimensionId === dimensionId);
    if (!group) {
      group = { dimensionId, qualities: [] };
      groups.push(group);
    }
    let quality = group.qualities.find((q) => q.qualityId === qualityId);
    if (!quality) {
      quality = { qualityId, rows: [] };
      group.qualities.push(quality);
    }
    quality.rows.push(row);
  }
  return groups;
}

export function ClaimsByDimension({
  body,
  instrument,
  vocabulary,
  validity,
}: {
  body: ReportBody;
  instrument: InstrumentResponse | undefined;
  vocabulary: QualityReferenceResponse[] | undefined;
  validity?: Map<string, ClaimValidity>;
}) {
  if (body.generatorLevel.length === 0) {
    return (
      <section className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
        No course in this dataset names a known generator version, so there is nothing to
        read these claims for. The notes at the bottom say which courses.
      </section>
    );
  }
  if (!instrument) {
    return <p className="text-sm text-muted-foreground">Reading the instrument…</p>;
  }

  const qualityName = new Map((vocabulary ?? []).map((q) => [q.quality_id, q.quality_name]));
  const dimensionName = new Map(
    (vocabulary ?? [])
      .filter((q) => q.dimension_id)
      .map((q) => [q.dimension_id as string, q.dimension_name ?? q.dimension_id]),
  );
  const groups = groupClaims(body, instrument);
  const several = body.generatorLevel.length > 1;

  return (
    <div className="space-y-6">
      {groups.map((group) => {
        const claims = group.qualities.reduce((sum, q) => sum + q.rows.length, 0);
        return (
          <section key={group.dimensionId ?? "none"} className="rounded-lg border bg-card">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-3">
              <h3 className="font-medium">
                {group.dimensionId
                  ? (dimensionName.get(group.dimensionId) ?? group.dimensionId)
                  : "Not grouped under a dimension"}
              </h3>
              <span className="text-xs text-muted-foreground">
                {claims} {claims === 1 ? "claim" : "claims"} about {group.qualities.length}{" "}
                {group.qualities.length === 1 ? "quality" : "qualities"}
              </span>
            </div>
            <div className="divide-y">
              {group.qualities.map((quality) => (
                <div key={quality.qualityId ?? "none"} className="space-y-3 px-4 py-3">
                  <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    {quality.qualityId
                      ? (qualityName.get(quality.qualityId) ?? quality.qualityId)
                      : "No quality"}
                  </p>
                  <ul className="space-y-4">
                    {quality.rows.map((row) => (
                      <ClaimEntry
                        key={row.claimId}
                        row={row}
                        several={several}
                        validity={validity?.get(row.claimId)}
                      />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function ClaimEntry({
  row,
  several,
  validity,
}: {
  row: Row;
  several: boolean;
  validity: ClaimValidity | undefined;
}) {
  return (
    <li className="space-y-1.5 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1">{row.statement}</p>
        <ValidityBadge validity={validity} />
      </div>
      <p className="flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
        {row.claimId} <CopyButton value={row.claimId} />
      </p>
      {row.readings.map((reading) => (
        <Reading key={reading.label} label={several ? reading.label : null} claim={reading.claim} />
      ))}
    </li>
  );
}

function Reading({
  label,
  claim,
}: {
  label: string | null;
  claim: StudyReportGeneratorClaim | null;
}) {
  if (!claim) {
    return (
      <p className="text-xs italic text-muted-foreground">
        {label ? `${label}: ` : ""}not measured
      </p>
    );
  }
  const supported = claim.distribution.supported ?? 0;
  const refuted = claim.distribution.refuted ?? 0;
  const insufficient = claim.distribution.insufficient ?? 0;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {label ? <span className="w-40 truncate text-xs text-muted-foreground">{label}</span> : null}
      <DistributionBar
        className="max-w-48"
        segments={[
          { key: "supported", count: supported, label: "supported", className: "bg-emerald-600" },
          { key: "refuted", count: refuted, label: "refuted", className: "bg-destructive" },
          { key: "insufficient", count: insufficient, label: "insufficient", className: "bg-amber-500" },
        ]}
      />
      <span className="text-xs tabular-nums text-muted-foreground">
        {supported} supported · {refuted} refuted · {insufficient} insufficient ·{" "}
        {claim.coverage.evaluated} of {claim.coverage.of} courses evaluated
        {claim.excludedNotApplicable ? ` · ${claim.excludedNotApplicable} not applicable` : ""}
      </span>
    </div>
  );
}
