import { DistributionBar } from "@/components/admin/distribution-bar";
import { byDimension } from "@/components/admin/campaign-report/ranking";
import type { CampaignReport, CampaignReportItem } from "@/lib/api/types";

/** What the panel said, grouped as the instrument groups it.
 *
 *  ADR-0052 §1 kept the `dimension` column for exactly this — *"a dimension is where
 *  qualities are read together, never where they are elicited"* — and until now nothing read
 *  it. Read together, never added together: there is no dimension-level number here, because
 *  a mean of means is the aggregate ADR-0011 retired wearing a heading.
 *
 *  Each item shows its distribution beside its mean rather than the mean alone. On a Likert
 *  scale those are not the same information: two experts at 2 and 5 average to the same 3.5
 *  as two at 3 and 4, and only one of those two courses has a problem.
 */
export function DimensionProfile({ report }: { report: CampaignReport }) {
  const groups = byDimension(report);
  const scale = range(report.instrument.scale_min, report.instrument.scale_max);

  return (
    <section className="space-y-4">
      {groups.map((group) => (
        <div key={group.dimension} className="rounded-lg border bg-card">
          <div className="border-b px-4 py-2">
            <h3 className="text-sm font-medium capitalize">
              {group.dimension.replaceAll("-", " ")}
            </h3>
          </div>
          <ul className="divide-y">
            {group.items.map((item) => (
              <ItemRow key={item.quality_id} item={item} scale={scale} scope={report.quorum.contents_in_scope} />
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function ItemRow({
  item,
  scale,
  scope,
}: {
  item: CampaignReportItem;
  scale: number[];
  scope: number;
}) {
  const segments = scale.map((point) => ({
    key: String(point),
    count: item.summary.distribution[String(point)] ?? 0,
    label: `answered ${point}`,
    className: SHADE[point] ?? "bg-muted-foreground",
  }));

  return (
    <li className="grid gap-2 px-4 py-3 text-sm sm:grid-cols-[1fr_10rem_4rem] sm:items-center">
      <span className="min-w-0" title={item.quality_id}>
        <span className="block">{item.prompt}</span>
        <span className="block text-xs text-muted-foreground">
          {item.summary.scored_count} answers over {item.summary.answered_contents} of {scope}{" "}
          courses
          {item.summary.withheld_contents > 0
            ? ` · ${item.summary.withheld_contents} not asked`
            : ""}
          {item.summary.abstentions > 0 ? ` · ${item.summary.abstentions} abstained` : ""}
        </span>
      </span>
      <DistributionBar segments={segments} />
      <span className="text-right font-semibold tabular-nums sm:text-left">
        {item.summary.average === null ? (
          <span className="text-xs font-normal italic text-muted-foreground">not answered</span>
        ) : (
          item.summary.average.toFixed(2)
        )}
      </span>
    </li>
  );
}

/** Cool at the bottom of the scale, warm at the top — one ramp, so a bar is read as a
 *  direction rather than as a set of categories. */
const SHADE: Record<number, string> = {
  1: "bg-rose-600",
  2: "bg-orange-400",
  3: "bg-amber-300",
  4: "bg-emerald-400",
  5: "bg-emerald-600",
};

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, index) => from + index);
}
