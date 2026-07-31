import type { MetadataEntry } from "@/lib/api/types";

const LABELS: Record<string, string> = {
  learningObjectives: "Learning objectives",
  targetAudience: "Target audience",
  prerequisites: "Prerequisites",
};

function humanize(key: string) {
  return LABELS[key] ?? key.replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase());
}

/**
 * Reference panel the evaluator reads next to the course. It lives in a narrow column, so it
 * stacks in a single column: each entry is a labelled row separated by a hairline.
 */
export function MetadataList({ metadata }: { metadata: MetadataEntry[] }) {
  if (metadata.length === 0) {
    return <p className="text-sm text-muted-foreground">No metadata to show for this course.</p>;
  }

  return (
    <dl className="divide-y divide-border">
      {metadata.map((entry) => {
        const isList = Array.isArray(entry.value);
        return (
          <div key={entry.key} className="py-4 first:pt-0 last:pb-0">
            <dt className="mb-1.5 flex items-center gap-2 text-[0.6875rem] font-semibold uppercase tracking-wider text-muted-foreground">
              {humanize(entry.key)}
              {isList && (entry.value as string[]).length > 1 ? (
                <span className="rounded-full bg-muted px-1.5 py-px text-[0.625rem] tabular-nums">
                  {(entry.value as string[]).length}
                </span>
              ) : null}
            </dt>
            <dd className="text-sm leading-relaxed">
              {isList ? (
                (entry.value as string[]).length ? (
                  <ul className="space-y-2">
                    {(entry.value as string[]).map((v, i) => (
                      // Hanging indent: wrapped lines align with the text, not under the bullet.
                      <li key={i} className="relative pl-4">
                        <span
                          aria-hidden
                          className="absolute left-0 top-[0.5em] h-1.5 w-1.5 rounded-full bg-primary/50"
                        />
                        {v}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <Empty />
                )
              ) : entry.value ? (
                <p>{entry.value as string}</p>
              ) : (
                <Empty />
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function Empty() {
  return <span className="text-muted-foreground">—</span>;
}
