"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { CopyButton } from "@/components/admin/copy-button";
import { describeLocator } from "@/lib/locator";
import { cn } from "@/lib/utils";

/** The passage a judge actually read, in a container that fits it.
 *
 *  This is the most valuable thing a report carries and the easiest to ruin. A quote runs
 *  from a dozen characters to a couple of thousand; inlined raw it either buries the row it
 *  belongs to or gets clipped into uselessness. So: one line in a summary, and on demand the
 *  whole thing in a box that scrolls rather than one that grows.
 *
 *  The locator goes ABOVE the quote, not beside it. "artifact syllabus · lesson 3" is
 *  usually the entire answer a reader wanted and costs two lines where the passage costs
 *  forty — putting it first means the common case never needs the expansion at all. */
export function EvidenceQuote({
  quote,
  locator,
  absentCause,
}: {
  quote: string | null;
  locator?: Record<string, unknown> | null;
  absentCause?: string | null;
}) {
  const [open, setOpen] = useState(false);

  if (quote === null) {
    return (
      <p className="text-xs italic text-muted-foreground">
        {absentCause ? `no quote — ${absentCause}` : "no quote"}
      </p>
    );
  }

  const where = locator ? describeLocator(locator) : null;

  return (
    <div className="space-y-1">
      {where ? (
        // Truncated: one locator shape carries the artifact's whole URL, which is worth
        // having and not worth three lines above a quote.
        <p
          className="truncate text-[11px] uppercase tracking-wide text-muted-foreground"
          title={where}
        >
          {where}
        </p>
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start gap-1 text-left text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronDown
          className={cn(
            "mt-0.5 h-3 w-3 shrink-0 transition-transform motion-reduce:transition-none",
            !open && "-rotate-90",
          )}
        />
        <span className={cn("min-w-0 flex-1", !open && "line-clamp-1")}>“{quote}”</span>
      </button>
      {open ? (
        <div className="space-y-1">
          {/* Scrolls rather than grows: a two-thousand-character passage must not push the
              rest of the report off the screen to be read. */}
          <div className="max-h-64 overflow-y-auto whitespace-pre-wrap break-words rounded border bg-muted/30 p-2 text-xs">
            {quote}
          </div>
          <CopyButton value={quote} label="copy the passage" />
        </div>
      ) : null}
    </div>
  );
}

/** The one-line form, for a table cell or a summary row where there is no room to expand. */
export function QuoteLine({ quote }: { quote: string | null }) {
  if (quote === null) return <span className="text-muted-foreground">—</span>;
  return <span className="line-clamp-1 text-xs text-muted-foreground">“{quote}”</span>;
}
