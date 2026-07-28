"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Step 2: consume the course. Many sites block framing with X-Frame-Options / CSP
 * frame-ancestors (08-code.md §8), and that failure is silent — the iframe just stays blank.
 * So we (a) always offer "open in a new tab", and (b) flip to a blocked notice if the frame
 * hasn't reported a load within a short window.
 */
export function ConsumeContent({ url }: { url: string }) {
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
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Review the full course before scoring. If it doesn&apos;t load below, open it in a new
          tab.
        </p>
        <a href={url} target="_blank" rel="noopener noreferrer">
          <Button variant="outline" size="sm" type="button">
            Open in new tab <ExternalLink className="h-4 w-4" />
          </Button>
        </a>
      </div>

      <div className="relative overflow-hidden rounded-lg border bg-muted/30">
        {blocked ? (
          <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
            <p className="text-sm font-medium">This course can&apos;t be embedded here</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              The site blocks embedding. Use the button above to open it in a new tab, then come
              back to score it.
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
            className="h-[60vh] w-full"
            onLoad={() => {
              setLoaded(true);
              setBlocked(false);
            }}
          />
        )}
      </div>
    </div>
  );
}
