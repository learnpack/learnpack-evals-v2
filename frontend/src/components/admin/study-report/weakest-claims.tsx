import { ClaimStatusBadge } from "@/components/admin/claim-status";
import { CopyButton } from "@/components/admin/copy-button";
import { DistributionBar } from "@/components/admin/distribution-bar";
import { rankClaims } from "@/components/admin/study-report/rollup";
import type { ReportBody } from "@/lib/api/types";

/** Which assertions about the generator did not hold, worst first.
 *
 *  The claim's own sentence is the row label. Its id sits at the end as something to copy,
 *  because cross-referencing with the instrument's YAML is a real need and a different one
 *  from reading the page.
 *
 *  A distribution and its coverage, never a score: three courses refuted out of four judged
 *  is a different fact from three out of twenty, and one number cannot hold both. */
export function WeakestClaims({ body }: { body: ReportBody }) {
  const rows = rankClaims(body);
  if (rows.length === 0) {
    return (
      <section className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
        <h3 className="mb-1 font-medium text-foreground">Claims</h3>
        No generator-level accumulation: no course in this dataset names a known generator
        version, so there is nothing to attribute these claims to. The caveats below name
        which courses.
      </section>
    );
  }

  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-medium">Weakest claims</h3>
        <p className="text-xs text-muted-foreground">
          What the instrument asserts about the generator, ordered by how often the dataset
          refuted it.
        </p>
      </div>
      <ul className="divide-y">
        {rows.map((claim) => {
          const refuted = claim.distribution.refuted ?? 0;
          const supported = claim.distribution.supported ?? 0;
          const insufficient = claim.distribution.insufficient ?? 0;
          return (
            <li key={`${claim.generatorLabel}-${claim.claimId}`} className="px-4 py-3 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="min-w-0 flex-1" title={claim.claimId}>
                  {claim.statement}
                </p>
                <ClaimStatusBadge status={refuted > 0 ? "refuted" : supported > 0 ? "supported" : "insufficient"}>
                  {refuted > 0 ? `${refuted} refuted` : supported > 0 ? "held" : "undecided"}
                </ClaimStatusBadge>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <DistributionBar
                  className="max-w-56"
                  segments={[
                    { key: "supported", count: supported, label: "supported", className: "bg-emerald-600" },
                    { key: "refuted", count: refuted, label: "refuted", className: "bg-destructive" },
                    { key: "insufficient", count: insufficient, label: "insufficient", className: "bg-amber-500" },
                  ]}
                />
                <span className="text-xs tabular-nums text-muted-foreground">
                  {claim.coverage.evaluated} of {claim.coverage.of} courses judged
                  {claim.excludedNotApplicable
                    ? ` · ${claim.excludedNotApplicable} not applicable`
                    : ""}
                  {claim.notEvaluated ? ` · ${claim.notEvaluated} not evaluated` : ""}
                </span>
                <span className="ml-auto flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{claim.generatorLabel}</span>
                  <CopyButton value={claim.claimId} />
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
