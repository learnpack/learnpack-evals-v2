"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CopyButton } from "@/components/ui/copy-button";
import { EvidenceQuote, QuoteLine } from "@/components/admin/evidence-quote";
import { TALLY_LABEL, TALLY_ORDER, TALLY_VARIANT } from "@/components/admin/outcome-badge";
import { rankCriteria, type CriterionRow } from "@/components/admin/study-report/rollup";
import { cn } from "@/lib/utils";
import type { CriterionOutcomes, InstrumentResponse, OutcomeTally } from "@/lib/api/types";

/** Which check fails most across the dataset — the question that turns a round into an edit.
 *
 *  It could not be asked before: the report carries findings only for failures, so counting
 *  them gave a number with no denominator, which is the arithmetic ADR-0011 retired. The
 *  criteria here come from the instrument, so every one has a denominator whether or not
 *  anything judged it.
 *
 *  Expanding a row is where the reader's decision forks, and the row says so: the criterion
 *  can be right about a bad course, or wrong about a good one, and those lead to different
 *  places — an edit of the generator, or a calibration run against the instrument. */
export function CriteriaRollup({
  outcomes,
  instrument,
  externalIdOf,
}: {
  outcomes: CriterionOutcomes;
  instrument: InstrumentResponse | undefined;
  externalIdOf: (contentId: string) => string;
}) {
  const rows = rankCriteria(outcomes, instrument);
  if (rows.length === 0) return null;

  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-medium">Most-failed criteria</h3>
        <p className="text-xs text-muted-foreground">
          Every check the pinned instrument declares, over the whole dataset. Nothing is
          summed across criteria — each row carries its own denominator.
        </p>
      </div>
      <ul className="divide-y">
        {rows.map((row) => (
          <CriterionEntry
            key={row.criterionId}
            row={row}
            instrumentVersionId={outcomes.instrumentVersionId}
            externalIdOf={externalIdOf}
          />
        ))}
      </ul>
    </section>
  );
}

function CriterionEntry({
  row,
  instrumentVersionId,
  externalIdOf,
}: {
  row: CriterionRow;
  instrumentVersionId: string | null;
  externalIdOf: (contentId: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const failing = row.cells.filter((cell) => cell.outcome === "fail");

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
          <span className="block" title={row.criterionId}>
            {row.statement ?? row.criterionId}
          </span>
          <span className="block text-xs text-muted-foreground">
            {row.assessed === 0
              ? `nothing judged this — 0 of ${row.inDataset} courses assessed`
              : `failed in ${row.failed} of ${row.assessed} courses assessed`}
            {row.assessed > 0 && row.assessed < row.inDataset
              ? ` · ${row.inDataset - row.assessed} of the dataset unjudged`
              : ""}
          </span>
          {!open && row.exemplar ? <QuoteLine quote={row.exemplar.quote} /> : null}
        </span>
        <Partition distribution={row.distribution} />
      </button>

      {open ? (
        <div className="space-y-4 border-t bg-muted/20 px-4 py-3">
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              It passes when
            </p>
            <p className="text-sm">
              {row.passCondition ?? (
                <span className="italic text-muted-foreground">
                  the pinned instrument version does not spell one out
                </span>
              )}
            </p>
          </div>

          {row.failureModes.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Declared failure modes
              </p>
              <ul className="list-inside list-disc space-y-0.5 text-sm text-muted-foreground">
                {row.failureModes.map((mode) => (
                  <li key={mode}>{mode}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {failing.length === 0 ? (
            <p className="text-sm text-muted-foreground">No course failed this one.</p>
          ) : (
            <ul className="space-y-3">
              {failing.map((cell) => (
                <li key={cell.contentId} className="space-y-1 rounded border bg-background p-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{externalIdOf(cell.contentId)}</span>
                    {cell.failureMode ? (
                      <span className="text-xs text-destructive">{cell.failureMode}</span>
                    ) : null}
                    {cell.derived ? (
                      <Badge variant="outline">derived from absence</Badge>
                    ) : null}
                  </div>
                  <EvidenceQuote
                    quote={cell.quote}
                    locator={cell.locator}
                    absentCause={cell.derived ? "the absence IS the finding" : null}
                  />
                </li>
              ))}
            </ul>
          )}

          {/* The fork, said out loud. A failing criterion is either a true finding about the
              course or a badly written check, and the two lead to different places. */}
          <div className="flex flex-wrap items-center gap-2 border-t pt-3 text-xs">
            <span className="text-muted-foreground">Is this the generator, or the check?</span>
            <CopyButton value={row.criterionId} label="copy the criterion id" />
            {instrumentVersionId && failing[0] ? (
              <Link
                href={{
                  pathname: "/admin/calibration",
                  query: {
                    content: failing[0].contentId,
                    instrument: instrumentVersionId,
                    criterion: row.criterionId,
                  },
                }}
                className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5 hover:bg-accent"
              >
                <FlaskConical className="h-3 w-3" /> try it in calibration
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </li>
  );
}

/** The six states as badges, zero counts omitted — a `0 pass` chip is noise, and the
 *  coverage line above already says what was not judged. */
function Partition({ distribution }: { distribution: Record<OutcomeTally, number> }) {
  const present = TALLY_ORDER.filter((state) => distribution[state] > 0);
  if (present.length === 0) return null;
  return (
    <span className="hidden shrink-0 flex-wrap items-center gap-1 sm:flex">
      {present.map((state) => (
        <Badge key={state} variant={TALLY_VARIANT[state]}>
          {distribution[state]} {TALLY_LABEL[state]}
        </Badge>
      ))}
    </span>
  );
}
