import type { MetadataEntry } from "@/lib/api/types";

const LABELS: Record<string, string> = {
  learningObjectives: "Learning objectives",
  targetAudience: "Target audience",
  prerequisites: "Prerequisites",
};

function humanize(key: string) {
  return LABELS[key] ?? key.replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase());
}

export function MetadataList({ metadata }: { metadata: MetadataEntry[] }) {
  if (metadata.length === 0) {
    return <p className="text-sm text-muted-foreground">No metadata to show for this course.</p>;
  }

  return (
    <dl className="grid gap-4 sm:grid-cols-2">
      {metadata.map((entry) => (
        <div key={entry.key}>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {humanize(entry.key)}
          </dt>
          <dd className="mt-1 text-sm">
            {Array.isArray(entry.value) ? (
              entry.value.length ? (
                <ul className="list-inside list-disc space-y-0.5">
                  {entry.value.map((v, i) => (
                    <li key={i}>{v}</li>
                  ))}
                </ul>
              ) : (
                <span className="text-muted-foreground">—</span>
              )
            ) : (
              <span>{entry.value || <span className="text-muted-foreground">—</span>}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
