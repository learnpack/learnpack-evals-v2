"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, ExternalLink } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
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
 * **The frame waits for the session, and for the theme.** Rendering the bare URL first and
 * swapping it in would load the course twice and, worse, leave the first load without AI —
 * which is the state this whole mechanism exists to avoid. The theme is the same shape of
 * problem: it is also spelled into the URL, and it is also unknown until the browser has run
 * (the choice lives there, not on the server).
 *
 * Two silences that would otherwise show as a blank frame, and both are stated:
 *
 * - **Framing refused.** Many sites block embedding with X-Frame-Options / CSP
 *   frame-ancestors (08-code.md §8), and that failure is silent. So we flip to a blocked
 *   notice if the frame hasn't reported a load within a short window; the frame's own bar
 *   always offers "open in a new tab" too.
 * - **Nothing to frame.** A content may declare no deployed instance (ADR-0028) — `url` is
 *   null. It cannot fall through to the iframe: an empty src resolves to the current document,
 *   `onLoad` fires, and the evaluator would get a recursive blank frame with no explanation.
 *
 * A **missing session** is the third thing that can go wrong and is deliberately *not* said
 * here. The course loads and its AI refuses, which costs the evaluator only the exercises —
 * and they have already been told, in as many words, that completing those is not required.
 * A permanent banner over the course to pre-empt something they were told not to do was the
 * most expensive line on the screen: on a developer's machine it is always up, since local
 * auth mints no session at all, and everywhere else it explains a failure most evaluators
 * will never reach. `ai_session` and `reason` still come back on the response for whoever
 * has to diagnose one.
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
 * viewport). Its **width** is this component's, because the number comes from the course and
 * not from our layout — see `COURSE_MAX_WIDTH`.
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
  // Undefined until this has mounted in the browser, which is why the frame waits for it.
  const { resolvedTheme } = useTheme();
  const theme: CourseTheme | null = resolvedTheme ? asCourseTheme(resolvedTheme) : null;
  const [blocked, setBlocked] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // The session's URL when we have one, the assignment's plain URL when the request failed.
  const src = session ? session.url : isPending ? null : url;

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
        "relative mx-auto flex w-full flex-col overflow-hidden rounded-xl border bg-muted/30 shadow-sm",
        COURSE_MAX_WIDTH,
        "min-h-[320px]",
        className,
      )}
    >
      {isPending || !theme ? (
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
          {/* The one place the course cannot name itself, so this is what there is to quote. */}
          <p className="text-xs text-muted-foreground">{title}</p>
        </div>
      ) : blocked ? (
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 py-16 text-center">
          <p className="text-sm font-medium">This course can&apos;t be embedded here</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            The site blocks embedding. Open it in a new tab and score it from this page.
          </p>
          <p className="text-xs text-muted-foreground">{title}</p>
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
            <BookOpen className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <p className="min-w-0 truncate text-xs font-medium">
              The course — as a learner sees it
            </p>
            <CourseMap />
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
          <iframe
            // Re-keyed by theme: the course is told which one it is in when it loads and
            // never after, so the only way to move it is to load it again.
            key={theme}
            src={embedded(src, theme)}
            title={`${title} — the course being reviewed`}
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

/**
 * The widest the course is worth giving, and it is the course's own number.
 *
 * The player centres itself at `min(100%, 1111px)` — that is the measure its lessons are set
 * for. Embedded, it drops that: `#main-container.iframe-mode` overrides the width with
 * `100vw`, on the assumption that whoever embeds it has already chosen how wide the frame
 * should be. So this is us choosing, and the honest choice is the width the course would have
 * given itself.
 *
 * Left wide it is not merely long-lined. The lesson list opens as a 460px column beside a
 * content pane fixed at 65%, in a row that does not wrap: past about 1400px those two stop
 * adding up to the whole and leave a strip of dead ground on the right. Under this cap the row
 * is over-full, the two columns shrink to fit, and the strip cannot appear.
 *
 * The two-column layout already hands the frame less than this, so the cap is only felt in
 * focus mode — which is exactly where there was nothing else to bound it.
 */
const COURSE_MAX_WIDTH = "max-w-[1111px]";

/** The two themes the course platform accepts, spelled the way it spells them. */
type CourseTheme = "light" | "dark";

/** Anything that is not its own word for dark is light — including `system`, which is a
 *  question about a device and not a theme. */
function asCourseTheme(theme: string): CourseTheme {
  return theme === "dark" ? "dark" : "light";
}

/**
 * Ask the course to render as an embedded course, in the theme of the page around it.
 *
 * A LearnPack course takes query parameters for both. `iframe=true` drops the chrome that
 * makes no sense inside somebody else's page — the language selector and the theme switch —
 * and `theme` is what replaces the second of them: the switch is gone because the course is no
 * longer the one deciding, not because nobody is (ADR-0066). The platform validates the value
 * against its own two words and silently ignores anything else, so it is spelled here and
 * nowhere else.
 *
 * **Here and not in the backend, and not on the link out.** The URL the backend mints is also
 * what "open in new tab" opens, and a course opened in its own tab is not embedded: hiding its
 * language there, or holding it to this page's theme, would be wrong. Being embedded is known
 * only by whoever embeds. Applied to the fallback URL too, which is the other thing the
 * backend could not reach.
 *
 * Hand-built rather than parsed and re-encoded, for the reason the backend's own appender
 * gives: the stored URL is what an operator declared and what the platform serves, and a round
 * trip through a query parser can reorder or re-escape it into something subtly different.
 */
function embedded(url: string, theme: CourseTheme): string {
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}iframe=true&theme=${theme}`;
}

/**
 * How to move around inside a course nobody has seen before.
 *
 * Three things an evaluator cannot discover by looking, and the last of them is the one that
 * strands somebody: on a lesson that carries code the course hides its own forward button once
 * it has room for the editor, and we have told this reader they do not need to solve the
 * exercise — so they are standing on a lesson with no visible way out.
 *
 * That last one is worded as *may* on purpose. The course hides the button above 769px, and
 * what it measures is the frame's width, not the screen's: on a narrow laptop, or with the
 * form beside it, the same lesson can keep the button. Only the arrows are always there.
 *
 * **A link on the bar rather than a strip under the frame.** Somebody who cannot find their
 * way is looking at the top of the course, not at the bottom of our card — which on a laptop
 * is the part they would have to scroll to reach. A modal also costs the frame no height,
 * and this is read once.
 *
 * **Named after the question, not after the topic.** All three notes are one thing — the
 * lesson list, the arrows and the missing button are three ways of getting from one lesson to
 * the next — so the label can be as literal as the reader's own question. It carries no idiom
 * and no phrasal verb on purpose: a panel reading English is not a panel that grew up in it.
 *
 * It says where things are. It does **not** say what the course's controls are not: a
 * disclaimer beside somebody else's product buys a sentence of doubt for every button it does
 * not name.
 */
function CourseMap() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="shrink-0 rounded-md px-1.5 py-0.5 text-xs font-medium text-primary underline-offset-2 transition-colors hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        How to move between lessons
      </button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="How to move between lessons"
      >
        <ul className="list-disc space-y-2.5 pl-5 text-sm text-muted-foreground">
          <li>The lesson list is behind the menu icon at the top right of the course.</li>
          <li>The arrows at the top left move between lessons.</li>
          <li>
            On lessons with code the course&apos;s own Continue button may not be there — the
            arrows always are.
          </li>
        </ul>
      </Dialog>
    </>
  );
}
