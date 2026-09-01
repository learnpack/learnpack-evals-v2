"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCourseSession } from "@/lib/api/hooks";
import type { Uuid } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * The course itself, with the session that turns it from readable into usable.
 *
 * The AI inside a LearnPack course refuses to grade an open question or run an exercise
 * without a session belonging to a real person on its platform, so the backend mints one and
 * returns the course URL with it already in it (ADR-0061). The evaluator sees none of that;
 * they signed in once, with Clerk.
 *
 * **The frame waits for the session.** Rendering the bare URL first and swapping it in would
 * load the course twice and, worse, leave the first load without AI — which is the state
 * this whole mechanism exists to avoid.
 *
 * Three silences, all stated rather than shown as a blank frame:
 *
 * - **Framing refused.** Many sites block embedding with X-Frame-Options / CSP
 *   frame-ancestors (08-code.md §8), and that failure is silent. So we flip to a blocked
 *   notice if the frame hasn't reported a load within a short window; the page toolbar always
 *   offers "open in a new tab" too.
 * - **Nothing to frame.** A content may declare no deployed instance (ADR-0028) — `url` is
 *   null. It cannot fall through to the iframe: an empty src resolves to the current document,
 *   `onLoad` fires, and the evaluator would get a recursive blank frame with no explanation.
 * - **No session.** The course loads and its AI will refuse. Said in a strip above the frame
 *   rather than in place of it, because a course without AI is still most of a course, and
 *   hiding it would cost more than the exercises the evaluator cannot run.
 *
 * `url` is the plain consumable URL from the assignment, kept as a fallback: if the session
 * request itself fails, the evaluator still gets the course.
 *
 * The frame fills whatever height the parent gives it (the evaluation page pins it to the
 * viewport), so this component only owns the box, not its size.
 */
export function ConsumeContent({
  url,
  assignmentId,
  className,
}: {
  url: string | null;
  assignmentId: Uuid;
  className?: string;
}) {
  const { data: session, isPending } = useCourseSession(assignmentId);
  const [blocked, setBlocked] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // The session's URL when we have one, the assignment's plain URL when the request failed.
  const src = session ? session.url : isPending ? null : url;
  const withoutAi = session && session.url !== null && !session.ai_session;

  useEffect(() => {
    if (!src) return; // nothing will ever load: the blocked path would misname the cause
    timer.current = setTimeout(() => {
      if (!loaded) setBlocked(true);
    }, 3500);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [loaded, src]);

  return (
    <div
      className={cn(
        "relative flex min-h-[320px] flex-col overflow-hidden rounded-xl border bg-muted/30 shadow-sm",
        className,
      )}
    >
      {isPending ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-16 text-center">
          <p className="text-sm text-muted-foreground">Opening the course…</p>
        </div>
      ) : !src ? (
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
          <a href={src} target="_blank" rel="noopener noreferrer">
            <Button size="sm" type="button">
              Open course <ExternalLink className="h-4 w-4" />
            </Button>
          </a>
        </div>
      ) : (
        <>
          {withoutAi ? (
            <div className="flex items-start gap-2 border-b bg-amber-50 px-3 py-2 text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0" />
              <p className="text-xs">
                The AI inside this course is unavailable, so exercises and open questions
                won&apos;t be graded. Everything else works — score what you can see, and tell
                an admin.
                {session?.reason ? (
                  <span className="block opacity-80">{session.reason}</span>
                ) : null}
              </p>
            </div>
          ) : null}
          <iframe
            src={src}
            title="Course content"
            className="h-full w-full flex-1"
            onLoad={() => {
              setLoaded(true);
              setBlocked(false);
            }}
          />
        </>
      )}
    </div>
  );
}
