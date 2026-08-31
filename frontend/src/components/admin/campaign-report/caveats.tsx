import { silences } from "@/components/admin/campaign-report/ranking";
import type { CampaignReport } from "@/lib/api/types";

/** What is missing from the numbers above, and why — said here rather than left to the ADRs.
 *
 *  Two of these are decisions somebody already took and wrote down as a cost (ADR-0052), and
 *  a report that does not repeat them relies on its reader remembering an ADR while looking
 *  at a chart. That is not a reasonable thing to rely on.
 */
export function Caveats({ report }: { report: CampaignReport }) {
  const gaps = silences(report);
  const partial = gaps.declarationBound.filter((item) => item.asked < item.of);

  return (
    <section className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-medium">What these numbers do not cover</h3>
      </div>
      <ul className="divide-y text-sm">
        <Row
          label="Not asked"
          value={gaps.withheld}
          detail="item-and-course pairs where the course declares nothing the item is about, so nobody was put in front of it and the value was derived (ADR-0053). A generator's omission, not a gap in the panel."
        />
        <Row
          label="Could not judge"
          value={gaps.abstained}
          detail="answers where the expert looked and abstained. Off the scale on purpose: 1 means the course does not do this, and an abstention is a different statement."
        />
        <Row
          label="Awaiting answers"
          value={gaps.awaiting}
          detail="courses that have not reached their quorum. Their items contribute nothing to agreement yet."
        />
        <Row
          label="Corrections"
          value={report.quorum.superseded_count}
          detail="re-evaluations that supersede an earlier answer. Shown inside each course, excluded from every number above."
        />

        {partial.length > 0 ? (
          <li className="px-4 py-3">
            <p className="font-medium">Items that depend on a declaration</p>
            <p className="mt-1 text-xs text-muted-foreground">
              These were only put to an expert where the course declares what they rest on, so
              they are judged on a smaller set than the rest and their agreement is
              correspondingly weaker. The mix of the scope is a measurement decision here, not
              only a sampling one.
            </p>
            <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
              {partial.map((item) => (
                <li key={item.criterionId}>
                  <span className="text-foreground">{item.prompt}</span> — asked on {item.asked}{" "}
                  of {item.of} courses
                </li>
              ))}
            </ul>
          </li>
        ) : null}

        <li className="px-4 py-3">
          <p className="font-medium">The panel and the instrument did not read the same
            artefact</p>
          <p className="mt-1 text-xs text-muted-foreground">
            The experts judged the deployed, processed course; the automated instrument reads
            the draft. The lesson prose is the same text, so most items are unaffected — but
            the assessment item is not: a delivered challenge was read on one side and a
            proposal on the other. Any comparison of that item across the two sides carries
            this as a declared alternative explanation.
          </p>
        </li>
      </ul>
    </section>
  );
}

function Row({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <span className="w-10 shrink-0 text-lg font-semibold tabular-nums">{value}</span>
      <span className="min-w-0">
        <span className="block font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{detail}</span>
      </span>
    </li>
  );
}
