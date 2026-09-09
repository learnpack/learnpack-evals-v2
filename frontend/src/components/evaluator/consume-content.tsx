"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown, ExternalLink, MonitorPlay, Sparkles } from "lucide-react";
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
 * **The frame is given chrome of our own.** An iframe mounted bare reads as one more region of
 * this page, so an evaluator who has never seen a LearnPack course takes its controls for ours
 * — the first one asked whether its `Continue` meant "continue evaluating". We cannot change
 * what is inside, so the fix is to frame it: a bar above that says whose it is, a border, a
 * ground of its own, and the course's name in the frame's accessible title.
 *
 * The frame fills whatever height the parent gives it (the evaluation page pins it to the
 * viewport), so this component only owns the box, not its size.
 */
export function ConsumeContent({
  url,
  title,
  assignmentId,
  className,
}: {
  url: string | null;
  /** What to call the course — the label the page already shows in its heading (ADR-0059). */
  title: string;
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
          {/* Whose half of the screen this is. It names the course rather than the product:
              an evaluator is never told which platform serves it, only that what follows is
              the course itself and not part of the form beside it. */}
          <div className="flex items-center gap-2 border-b bg-muted/60 px-3 py-2">
            <MonitorPlay className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <p className="min-w-0 truncate text-xs font-medium">
              The course — as a learner sees it
            </p>
            {/* The action belongs to the frame, so it lives on the frame. */}
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Open in new tab <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
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
            title={`${title} — the course being reviewed`}
            className="h-full w-full flex-1"
            onLoad={() => {
              setLoaded(true);
              setBlocked(false);
            }}
          />
          <CourseMap />
        </>
      )}
    </div>
  );
}

/**
 * How to move around inside a course nobody has seen before.
 *
 * Three things an evaluator cannot discover by looking, and the last of them is the one that
 * strands somebody: on a lesson that carries code the course hides its own forward button on a
 * wide screen, and we have told this reader they do not need to solve the exercise — so they
 * are standing on a lesson with no visible way out.
 *
 * It sits under the frame, folded, and it says where things are. It does **not** say what the
 * course's controls are not: a disclaimer beside somebody else's product buys a sentence of
 * doubt for every button it does not name.
 */
function CourseMap() {
  const [open, setOpen] = useState(false);
  const bodyId = useId();

  return (
    <div className="border-t bg-muted/30">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 shrink-0 transition-transform motion-reduce:transition-none",
            !open && "-rotate-90",
          )}
        />
        Finding your way around the course
      </button>
      <ul
        id={bodyId}
        hidden={!open}
        className={cn(
          "list-disc space-y-1 px-3 pb-2.5 pl-8 text-xs text-muted-foreground",
          !open && "hidden",
        )}
      >
        <li>The lesson list is behind the menu icon at the top right of the course.</li>
        <li>The arrows at the top left move between lessons.</li>
        <li>
          On lessons with code the course hides its Continue button — use the arrows.
        </li>
      </ul>
    </div>
  );
}
