"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The course itself. Two different silences, both stated rather than shown as a blank frame:
 *
 * - **Framing refused.** Many sites block embedding with X-Frame-Options / CSP
 *   frame-ancestors (08-code.md §8), and that failure is silent. So we flip to a blocked
 *   notice if the frame hasn't reported a load within a short window; the page toolbar always
 *   offers "open in a new tab" too.
 * - **Nothing to frame.** A content may declare no deployed instance (ADR-0028) — `url` is
 *   null. It cannot fall through to the iframe: an empty src resolves to the current document,
 *   `onLoad` fires, and the evaluator would get a recursive blank frame with no explanation.
 *
 * The frame fills whatever height the parent gives it (the evaluation page pins it to the
 * viewport), so this component only owns the box, not its size.
 */
export function ConsumeContent({ url, className }: { url: string | null; className?: string }) {
  const [blocked, setBlocked] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!url) return; // nothing will ever load: the blocked path would misname the cause
    timer.current = setTimeout(() => {
      if (!loaded) setBlocked(true);
    }, 3500);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [loaded, url]);

  return (
    <div
      className={cn(
        "relative min-h-[320px] overflow-hidden rounded-xl border bg-muted/30 shadow-sm",
        className,
      )}
    >
      {!url ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-16 text-center">
          <p className="text-sm font-medium">This course has no deployed instance</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            No consumable URL was declared when this version was registered, so there is
            nothing to open. Tell an admin — it can&apos;t be scored by hand until the course
            is deployed somewhere.
          </p>
        </div>
      ) : blocked ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-16 text-center">
          <p className="text-sm font-medium">This course can&apos;t be embedded here</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            The site blocks embedding. Open it in a new tab and score it from this page.
          </p>
          <a href={url} target="_blank" rel="noopener noreferrer">
            <Button size="sm" type="button">
              Open course <ExternalLink className="h-4 w-4" />
            </Button>
          </a>
        </div>
      ) : (
        <iframe
          src={url}
          title="Course content"
          className="h-full w-full"
          onLoad={() => {
            setLoaded(true);
            setBlocked(false);
          }}
        />
      )}
    </div>
  );
}
