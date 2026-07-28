"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The course itself. Many sites block framing with X-Frame-Options / CSP frame-ancestors
 * (08-code.md §8), and that failure is silent — the iframe just stays blank. So we flip to a
 * blocked notice if the frame hasn't reported a load within a short window; the page toolbar
 * always offers "open in a new tab" too.
 *
 * The frame fills whatever height the parent gives it (the evaluation page pins it to the
 * viewport), so this component only owns the box, not its size.
 */
export function ConsumeContent({ url, className }: { url: string; className?: string }) {
  const [blocked, setBlocked] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    timer.current = setTimeout(() => {
      if (!loaded) setBlocked(true);
    }, 3500);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [loaded]);

  return (
    <div
      className={cn(
        "relative min-h-[320px] overflow-hidden rounded-xl border bg-muted/30 shadow-sm",
        className,
      )}
    >
      {blocked ? (
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
