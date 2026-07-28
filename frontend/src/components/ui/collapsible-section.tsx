"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  title: string;
  /** Short hint next to the title (e.g. "6 criteria"). */
  badge?: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  contentClassName?: string;
  children: ReactNode;
}

/**
 * Card-shaped disclosure. Open by default: the evaluator sees everything at once and
 * collapses what they don't need to give the course more room.
 */
export function CollapsibleSection({
  title,
  badge,
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
          className="flex w-full items-center justify-between gap-3 rounded-xl px-5 py-4 text-left transition-colors hover:bg-accent/40"
        >
          <span className="flex items-baseline gap-2">
            <span className="font-semibold tracking-tight">{title}</span>
            {badge ? <span className="text-xs text-muted-foreground">{badge}</span> : null}
          </span>
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
              !open && "-rotate-90",
            )}
          />
        </button>
      </h2>
      {open ? <div className={cn("px-5 pb-5", contentClassName)}>{children}</div> : null}
    </section>
  );
}
