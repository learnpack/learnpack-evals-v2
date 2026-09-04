import { Badge } from "@/components/ui/badge";
import type { CampaignReport, GoldenStatus } from "@/lib/api/types";

/** What the campaign has produced so far, in four numbers and one verdict.
 *
 *  The golden badge belongs here rather than on the management page: whether this round can
 *  serve as the human reference is the campaign's **output**, not a control somebody
 *  operates. Everything else on this row is the coverage that decides it.
 */
export function Verdict({
  report,
  golden,
}: {
  report: CampaignReport;
  golden: GoldenStatus | undefined;
}) {
  const { quorum } = report;

  return (
    <section className="rounded-lg border bg-card">
      <div className="grid gap-px overflow-hidden rounded-t-lg bg-border sm:grid-cols-3">
        <Figure
          label="Courses complete"
          value={`${quorum.contents_complete}/${quorum.contents_in_scope}`}
          detail={`${Math.round(quorum.coverage * 100)}% of the scope reached quorum`}
        />
        <Figure
          label="Evaluations"
          value={`${quorum.evaluations_counted}/${quorum.evaluations_expected}`}
          detail={`${quorum.required_per_content} required per course`}
        />
        <Figure
          label="Experts"
          value={String(quorum.assessor_count)}
          detail="with an active assignment in this round"
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div>
          <p className="text-sm font-medium">Usable as the human reference</p>
          <p className="text-xs text-muted-foreground">
            {golden
              ? `Coverage ${Math.round(golden.coverage * 100)}% against a threshold of ${Math.round(
                  golden.threshold * 100,
                )}%${
                  golden.established_at
                    ? ` · established ${new Date(golden.established_at).toLocaleDateString()}`
                    : ""
                }`
              : "Checking…"}
          </p>
        </div>
        {golden ? (
          golden.usable ? (
            <Badge variant="success">usable</Badge>
          ) : (
            <Badge variant="outline">not yet</Badge>
          )
        ) : null}
      </div>
    </section>
  );
}

function Figure({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="bg-card px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}
