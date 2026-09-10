import type { MembershipSummary } from "@/lib/datasets";

/** What a membership is made of, in one line: totals first, then only what is missing.
 *
 * Shared by the dataset page, which reads a frozen version, and the course picker, which
 * reads the set while it is being composed — the same facts, before and after freezing. */
export function ReadinessLine({ summary }: { summary: MembershipSummary }) {
  const facts = [
    `${summary.total} ${summary.total === 1 ? "course" : "courses"}`,
    summary.undeployed ? `${summary.undeployed} not deployed` : null,
    summary.withoutBrief ? `${summary.withoutBrief} without a brief` : null,
    summary.generatorVersions
      ? `${summary.generatorVersions} generator ${summary.generatorVersions === 1 ? "version" : "versions"}`
      : null,
    summary.withoutGenerator ? `${summary.withoutGenerator} without a generator` : null,
    summary.formats.length > 1 ? summary.formats.join(" + ") : null,
  ].filter(Boolean);

  return <p className="text-sm text-muted-foreground">{facts.join(" · ")}</p>;
}
