import { Badge } from "@/components/ui/badge";
import type { DocumentSource, StudyGap } from "@/lib/api/types";

/** The one component that knows which of the two documents is on screen.
 *
 *  Everything below it renders `ReportBody`, which cannot tell them apart and does not need
 *  to. The distinction matters exactly once, at the top, and it matters a lot: a report is
 *  the artifact somebody signed, and a preview is what signing would produce. Reading one
 *  as the other is the misunderstanding this whole band exists to prevent. */
export function DocumentBand({ source }: { source: DocumentSource }) {
  if (source.kind === "frozen") {
    return (
      <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-card px-4 py-3 text-sm">
        <Badge variant="success">signed off</Badge>
        <span>
          Signed off {new Date(source.signedOffAt).toLocaleString()}
          {source.signedOffBy ? " · " : ""}
        </span>
        {source.signedOffBy ? (
          <span className="font-mono text-xs text-muted-foreground">{source.signedOffBy}</span>
        ) : null}
        <span className="text-muted-foreground">
          — immutable, and composed from exactly the judgments it records.
        </span>
      </div>
    );
  }

  const recomposed = source.kind === "recomposed";
  return (
    <div className="space-y-2 rounded-lg border border-dashed bg-muted/30 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="warning">{recomposed ? "recomposed" : "preview"}</Badge>
        <span className="text-muted-foreground">
          Composed {new Date(source.composedAt).toLocaleString()} from today&apos;s judgments.{" "}
          {recomposed
            ? "This study is already signed off: the report of record is the frozen one, and this recomposition may differ from it."
            : "Nothing is written until you sign off, and signing off freezes exactly this."}
        </span>
      </div>
      <Gaps gaps={source.gaps} />
    </div>
  );
}

/** What is missing, in the words the backend chose — a study still being set up says so
 *  rather than showing an empty report and letting the reader guess. */
function Gaps({ gaps }: { gaps: StudyGap[] }) {
  if (gaps.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {gaps.map((gap) => (
        <Badge key={gap.gap} variant="outline">
          {gap.gap.replaceAll("_", " ")}
        </Badge>
      ))}
    </div>
  );
}
