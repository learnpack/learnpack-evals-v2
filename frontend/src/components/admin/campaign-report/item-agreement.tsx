"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { rankItems, type RankedItem } from "@/components/admin/campaign-report/ranking";
import { cn } from "@/lib/utils";
import type { CampaignReport } from "@/lib/api/types";

/** Which items the experts read the same way — the campaign's own question (ADR-0052 §5).
 *
 *  This is the axis the report exists for. At the grain of a course, two assessors give one
 *  pair per item and every number is noise; pooled over the scope, the same item has as many
 *  pairs as there are courses two people both finished, and *that* is what says whether the
 *  item is answerable at all.
 *
 *  Worst first, because the reader's next act is rewriting an item, not admiring one.
 */
export function ItemAgreement({ report }: { report: CampaignReport }) {
  const rows = rankItems(report);

  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-medium">Where the experts disagreed</h3>
        <p className="text-xs text-muted-foreground">
          Every item of the pinned instrument, worst agreement first. Pairs are formed inside a
          single course — the only place two answers are about the same thing — and pooled
          across the scope. Nothing is summed across items.
        </p>
      </div>
      <ul className="divide-y">
        {rows.map((row) => (
          <ItemEntry key={row.criterion_id} row={row} scope={report.quorum.contents_in_scope} />
        ))}
      </ul>
    </section>
  );
}

function ItemEntry({ row, scope }: { row: RankedItem; scope: number }) {
  const [open, setOpen] = useState(false);
  const { agreement } = row.summary;
  const unpaired = agreement.pair_count === 0;

  return (
    <li className="text-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-2 px-4 py-3 text-left hover:bg-accent/40"
      >
        <ChevronDown
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
            !open && "-rotate-90",
          )}
        />
        <span className="min-w-0 flex-1 space-y-1">
          <span className="block" title={row.criterion_id}>
            {row.prompt}
          </span>
          <span className="block text-xs text-muted-foreground">
            {unpaired
              ? `no course was answered by two experts — 0 pairs over ${scope} courses`
              : `${agreement.pair_count} pairs over ${agreement.content_count} of ${scope} courses`}
            {row.summary.withheld_contents > 0
              ? ` · ${row.summary.withheld_contents} not asked`
              : ""}
            {row.summary.abstentions > 0 ? ` · ${row.summary.abstentions} abstained` : ""}
          </span>
        </span>
        <span className="hidden shrink-0 items-center gap-1 sm:flex">
          {unpaired ? (
            <Badge variant="outline">no pairs</Badge>
          ) : (
            <>
              <Badge variant={severity(agreement.mean_abs_diff)}>
                Δ {agreement.mean_abs_diff?.toFixed(2)}
              </Badge>
              <Badge variant="outline">{agreement.exact_pct?.toFixed(0)}% exact</Badge>
              <Badge variant="secondary">±1 {agreement.within_one_pct?.toFixed(0)}%</Badge>
            </>
          )}
        </span>
      </button>

      {open ? (
        <div className="space-y-3 border-t bg-muted/20 px-4 py-3 text-sm">
          <p className="text-xs text-muted-foreground">
            <span className="uppercase tracking-wide">{row.dimension}</span> ·{" "}
            <code className="text-xs">{row.criterion_id}</code>
          </p>

          {unpaired ? (
            <p className="text-muted-foreground">
              Nothing to compare yet. Agreement needs two experts to have finished the same
              course; a mean of 0 here would claim an agreement nobody demonstrated.
            </p>
          ) : (
            <dl className="grid gap-3 sm:grid-cols-4">
              <Stat term="Mean difference" value={agreement.mean_abs_diff?.toFixed(2) ?? "—"} />
              <Stat term="Exact agreement" value={`${agreement.exact_pct?.toFixed(0)}%`} />
              <Stat term="Within one point" value={`${agreement.within_one_pct?.toFixed(0)}%`} />
              <Stat term="Pairs" value={String(agreement.pair_count)} />
            </dl>
          )}

          {/* On a Likert scale the two percentages answer different questions, and reading the
              first without the second is how a usable item gets rewritten for nothing. */}
          {!unpaired && agreement.exact_pct !== null && agreement.within_one_pct !== null ? (
            <p className="text-xs text-muted-foreground">
              {agreement.within_one_pct - agreement.exact_pct >= 30
                ? "The experts largely agree on direction and differ on emphasis — adjacent answers, not opposed ones."
                : "Exact and within-one agreement are close, so the disagreements here are wide ones, not a matter of emphasis."}
            </p>
          ) : null}

          {row.required_data.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              This item is only put to an expert when the course declares{" "}
              {row.required_data.join(", ")} — {row.summary.withheld_contents} of {scope} courses
              declare none, and their value was derived rather than judged.
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function Stat({ term, value }: { term: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{term}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** Colour follows the size of the gap on a five-point scale, not a target nobody set. */
function severity(meanAbsDiff: number | null) {
  if (meanAbsDiff === null) return "outline" as const;
  if (meanAbsDiff >= 1.5) return "destructive" as const;
  if (meanAbsDiff >= 0.75) return "warning" as const;
  return "success" as const;
}
