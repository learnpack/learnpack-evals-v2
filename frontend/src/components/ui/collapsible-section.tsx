"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  title: string;
  /** Short hint next to the title (e.g. "6 criteria"). */
  badge?: ReactNode;
  /**
   * Read-at-a-glance summary, right-aligned before the chevron. Everything in the header is
   * inside the toggle, so `meta` must stay non-interactive: a control here would look
   * clickable and do something else (it would toggle the section).
   */
  meta?: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

/**
 * Card-shaped disclosure: the whole header row is the toggle.
 *
 * Open by default, because the first caller is the evaluator's rubric — they see everything
 * at once and collapse what they don't need. Callers listing many items pass
 * `defaultOpen={false}` and lean on `meta` to make the closed row worth scanning.
 */
export function CollapsibleSection({
  title,
  badge,
  meta,
  defaultOpen = true,
  className,
  contentClassName,
  children,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={cn("rounded-xl border bg-card text-card-foreground shadow-sm", className)}>
      <h2>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex w-full items-center justify-between gap-3 rounded-xl px-5 py-4 text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="truncate font-semibold tracking-tight">{title}</span>
            {badge ? (
              <span className="shrink-0 text-xs text-muted-foreground">{badge}</span>
            ) : null}
          </span>
          <span className="flex shrink-0 items-center gap-3">
            {meta}
            <ChevronDown
              className={cn(
                "h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
                !open && "-rotate-90",
              )}
            />
          </span>
        </button>
      </h2>
      {open ? <div className={cn("px-5 pb-5", contentClassName)}>{children}</div> : null}
    </section>
  );
}
