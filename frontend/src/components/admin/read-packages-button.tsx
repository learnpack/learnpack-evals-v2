"use client";

import { useState } from "react";
import { toast } from "sonner";
import { BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/states";
import { useProfileContent } from "@/lib/api/hooks";
import type { Uuid } from "@/lib/api/types";

/**
 * Reading packages now — wherever the console has just said one was never read.
 *
 * One request per course, looped here rather than batched in an endpoint (ADR-0035 §5):
 * each package is fetched and parsed, so a whole-set call would be a multi-minute write
 * with no progress and no bounded failure. And never automatic — the batch is a thing
 * somebody asks for (12-define: explicit, never a cascade).
 *
 * Refusals are answers, not crashes. A course already read comes back 409 and one this
 * path cannot fetch over http comes back 422; both are counted apart from a genuine
 * extraction failure, because calling them failures would blame the package.
 */
export function ReadPackagesButton({
  contentIds,
  label,
  variant = "outline",
}: {
  contentIds: Uuid[];
  label: string;
  variant?: "outline" | "default";
}) {
  const profile = useProfileContent();
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);

  async function run() {
    setProgress({ done: 0, total: contentIds.length });
    let read = 0;
    let failed = 0;
    let refused = 0;

    for (const contentId of contentIds) {
      try {
        const result = await profile.mutateAsync(contentId);
        if (result.status === "ok") read += 1;
        else failed += 1;
      } catch {
        refused += 1;
      }
      setProgress((previous) => (previous ? { ...previous, done: previous.done + 1 } : previous));
    }

    setProgress(null);
    const summary = [
      `${read} read`,
      failed ? `${failed} could not be read` : null,
      refused ? `${refused} skipped` : null,
    ]
      .filter(Boolean)
      .join(", ");
    if (failed || refused) toast.warning("Finished reading.", { description: summary });
    else toast.success("Finished reading.", { description: summary });
  }

  return (
    <Button size="sm" variant={variant} onClick={run} disabled={progress !== null}>
      {progress ? <Spinner /> : <BookOpen className="h-3.5 w-3.5" />}
      {progress ? `Reading ${progress.done + 1} of ${progress.total}…` : label}
    </Button>
  );
}
