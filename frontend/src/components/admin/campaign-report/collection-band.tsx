import { Badge } from "@/components/ui/badge";
import type { CampaignReport } from "@/lib/api/types";

/** Whether what is below is finished — the one thing a reader must know before the numbers.
 *
 *  A campaign report is composed on read and never frozen (ADR-0060 §7), so there is no
 *  signed/preview pair to distinguish, as there is for a study. What there is instead is a
 *  round still collecting answers, and a screenshot of it taken at 40% that will be quoted
 *  later as a result. This band is what stops that.
 */
export function CollectionBand({ report }: { report: CampaignReport }) {
  const { quorum } = report;
  const closed = report.status === "closed";
  const complete = quorum.evaluations_counted >= quorum.evaluations_expected;

  if (closed) {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card px-4 py-3 text-sm">
        <Badge variant="secondary">closed</Badge>
        <span className="text-muted-foreground">
          This round is over. Nothing more will be collected, so these numbers are the ones it
          produced — recomposed on read from the answers it holds, not a signed document.
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm">
      <Badge variant={complete ? "success" : "warning"}>open</Badge>
      <span className="text-muted-foreground">
        {complete
          ? "Every course has reached its quorum, but the campaign is still open — a late correction would move these numbers."
          : `Provisional: ${quorum.evaluations_counted} of ${quorum.evaluations_expected} evaluations are in. Read the agreement below as a work in progress.`}
      </span>
    </div>
  );
}
