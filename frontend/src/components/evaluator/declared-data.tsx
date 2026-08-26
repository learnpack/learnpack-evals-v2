"use client";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import type { DeclaredDatum } from "@/lib/api/types";

/**
 * What the course says about itself, for the items that rest on it (ADR-0057).
 *
 * Bounded by the instrument: only the data an asked item declares in `required_data` ever
 * arrives here. The rest of the profile — the lesson bodies, the inventory, the extraction's
 * own status — does not, and must not: the rater judges the course, they do not audit the
 * adapter. Nothing on this panel names a generator, a version or an adapter (ADR-0053).
 *
 * The heading is derived from the id rather than looked up in a label map. Two ids do not
 * justify a table of English that would then have to be kept in step with the instrument,
 * and `data_requirements.definition` is written for us, not for a rater.
 */
export function DeclaredData({ declared }: { declared: DeclaredDatum[] }) {
  if (declared.length === 0) return null;

  return (
    <CollapsibleSection title="What the course declares" badge={`${declared.length}`}>
      <p className="mb-4 text-xs text-muted-foreground">
        The course&apos;s own words, taken from how it defines itself. They may not appear in
        the pages you read.
      </p>
      <div className="space-y-4">
        {declared.map((datum) => (
          <div key={datum.requirement_id}>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {humanize(datum.requirement_id)}
            </p>
            {Array.isArray(datum.value) ? (
              <ul className="mt-1.5 list-disc space-y-1 pl-4 text-sm">
                {datum.value.map((statement, index) => (
                  <li key={index}>{statement}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1.5 text-sm">{datum.value}</p>
            )}
          </div>
        ))}
      </div>
    </CollapsibleSection>
  );
}

/** `learning_objectives` → `Learning objectives`. */
function humanize(requirementId: string): string {
  const words = requirementId.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
