"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ClaimStatusBadge } from "@/components/admin/claim-status";
import { CopyButton } from "@/components/admin/copy-button";
import { EvidenceQuote } from "@/components/admin/evidence-quote";
import { OutcomeBadge } from "@/components/admin/outcome-badge";
import { byCourse } from "@/components/admin/study-report/rollup";
import { cn } from "@/lib/utils";
import type {
  CriterionOutcomes,
  InstrumentResponse,
  ReportBody,
  StudyReportContent,
} from "@/lib/api/types";

/** Course by course — the layer that holds everything, and the reason the two above it can
 *  hold so little.
 *
 *  Collapsed by default and one row each. The screen this replaces rendered every course as
 *  an always-open card, so a twenty-course round was twenty expanded panels and no way to
 *  see which one to read first. */
export function CourseList({
  body,
  outcomes,
  instrument,
}: {
  body: ReportBody;
  outcomes: CriterionOutcomes | undefined;
  instrument: InstrumentResponse | undefined;
}) {
  if (body.contents.length === 0) return null;

  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-medium">Course by course</h3>
        <p className="text-xs text-muted-foreground">
          {body.contents.length} course{body.contents.length === 1 ? "" : "s"} in this
          dataset. Everything the judges recorded is in here.
        </p>
      </div>
      <ul className="divide-y">
        {body.contents.map((content) => (
          <CourseEntry
            key={content.contentId}
            content={content}
            outcomes={outcomes}
            instrument={instrument}
          />
        ))}
      </ul>
    </section>
  );
}

function CourseEntry({
  content,
  outcomes,
  instrument,
}: {
  content: StudyReportContent;
  outcomes: CriterionOutcomes | undefined;
  instrument: InstrumentResponse | undefined;
}) {
  const [open, setOpen] = useState(false);
  const claims = content.claims ?? [];
  const refuted = claims.filter((claim) => claim.status === "refuted").length;
  const insufficient = claims.filter((claim) => claim.status === "insufficient").length;

  return (
    <li className="text-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-accent/40"
      >
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
            !open && "-rotate-90",
          )}
        />
        <span className="min-w-0 flex-1 truncate font-medium">{content.externalId}</span>
        {!content.judgmentId ? (
          <Badge variant="outline">not judged</Badge>
        ) : (
          <>
            {refuted > 0 ? <Badge variant="destructive">{refuted} refuted</Badge> : null}
            {insufficient > 0 ? (
              <Badge variant="warning">{insufficient} undecided</Badge>
            ) : null}
            {refuted === 0 && insufficient === 0 ? (
              <Badge variant="success">every claim held</Badge>
            ) : null}
          </>
        )}
      </button>

      {open ? (
        <div className="space-y-4 border-t bg-muted/20 px-4 py-3">
          {!content.judgmentId ? (
            <p className="text-muted-foreground">
              No judgment when this document was composed — it counts in no distribution
              above, and the caveats say so.
            </p>
          ) : (
            <>
              <ClaimList claims={claims} />
              {outcomes ? (
                <CriterionTable
                  outcomes={outcomes}
                  instrument={instrument}
                  contentId={content.contentId}
                />
              ) : null}
            </>
          )}
          <Identifiers content={content} />
        </div>
      ) : null}
    </li>
  );
}

function ClaimList({ claims }: { claims: NonNullable<StudyReportContent["claims"]> }) {
  if (claims.length === 0) return null;
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Claims
      </p>
      <ul className="space-y-1">
        {claims.map((claim) => (
          <li key={claim.claimId} className="flex flex-wrap items-center gap-2 text-xs">
            <ClaimStatusBadge status={claim.status} />
            <span title={claim.claimId}>{claim.claimId}</span>
            {claim.insufficiencyCause ? (
              <span className="text-muted-foreground">({claim.insufficiencyCause})</span>
            ) : null}
            {/* The counts behind the status: a claim is only as good as what evidenced it. */}
            <span className="text-muted-foreground">
              {Object.entries(claim.evidenceBasis)
                .filter(([, count]) => count > 0)
                .map(([state, count]) => `${count} ${state}`)
                .join(" · ")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Every criterion this course produced an outcome for — passes included, with their
 *  quotes. That is the half no report could show before: findings exist one per FAILING
 *  criterion, so the passage a judge read to decide a pass had nowhere to go. */
function CriterionTable({
  outcomes,
  instrument,
  contentId,
}: {
  outcomes: CriterionOutcomes;
  instrument: InstrumentResponse | undefined;
  contentId: string;
}) {
  const rows = byCourse(outcomes, instrument, contentId);
  if (rows.length === 0) return null;

  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Criteria
      </p>
      <ul className="space-y-2">
        {rows.map((row) => (
          <li key={row.criterionId} className="space-y-1 rounded border bg-background p-2">
            <div className="flex flex-wrap items-start gap-2">
              <OutcomeBadge outcome={row.cell.outcome} />
              <span className="min-w-0 flex-1 text-xs" title={row.criterionId}>
                {row.statement ?? row.criterionId}
              </span>
            </div>
            {row.cell.executionCause ? (
              <p className="text-xs text-violet-700 dark:text-violet-400">
                {row.cell.executionCause.task ? `${row.cell.executionCause.task} — ` : ""}
                {row.cell.executionCause.kind}: {row.cell.executionCause.message}
              </p>
            ) : null}
            {row.cell.failureMode ? (
              <p className="text-xs text-destructive">{row.cell.failureMode}</p>
            ) : null}
            <EvidenceQuote quote={row.cell.quote} locator={row.cell.locator} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The ids, once, at the bottom, ready to copy. They are needed in an editor, not in a
 *  sentence — which is what lets every row above be readable. */
function Identifiers({ content }: { content: StudyReportContent }) {
  return (
    <div className="flex flex-wrap items-center gap-2 border-t pt-3">
      <span className="text-xs text-muted-foreground">Identifiers</span>
      <CopyButton value={content.contentId} label={`content ${content.contentId.slice(0, 8)}…`} />
      {content.judgmentId ? (
        <CopyButton
          value={content.judgmentId}
          label={`judgment ${content.judgmentId.slice(0, 8)}…`}
        />
      ) : null}
      {content.generatorVersionId ? (
        <CopyButton
          value={content.generatorVersionId}
          label={`generator ${content.generatorVersionId.slice(0, 8)}…`}
        />
      ) : (
        <span className="text-xs italic text-muted-foreground">generator declared unknown</span>
      )}
      {content.briefId ? (
        <CopyButton value={content.briefId} label={`brief ${content.briefId.slice(0, 8)}…`} />
      ) : null}
      {content.derivedAt ? (
        <span className="text-xs text-muted-foreground">
          judged {new Date(content.derivedAt).toLocaleString()}
        </span>
      ) : null}
    </div>
  );
}
