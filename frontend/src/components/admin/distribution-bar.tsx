/** A distribution as a bar, with its coverage beside it — never as a score.
 *
 *  ADR-0011 retired the single aggregate number, and a bar is the honest replacement: it
 *  shows the shape of a result without collapsing it into one figure that could be averaged
 *  against another. The counts stay readable in the title, so nothing here is only a colour.
 *
 *  A segment with a zero count renders nothing rather than a sliver: an invisible sliver is
 *  a lie about a value that is exactly none. */
export function DistributionBar({
  segments,
  className,
}: {
  segments: { key: string; count: number; label: string; className: string }[];
  className?: string;
}) {
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  if (total === 0) {
    return <span className="text-xs italic text-muted-foreground">nothing measured</span>;
  }

  return (
    <span
      className={`flex h-2 w-full min-w-16 overflow-hidden rounded-full bg-muted ${className ?? ""}`}
      title={segments
        .filter((segment) => segment.count > 0)
        .map((segment) => `${segment.count} ${segment.label}`)
        .join(" · ")}
    >
      {segments
        .filter((segment) => segment.count > 0)
        .map((segment) => (
          <span
            key={segment.key}
            className={segment.className}
            style={{ width: `${(segment.count / total) * 100}%` }}
          />
        ))}
    </span>
  );
}
