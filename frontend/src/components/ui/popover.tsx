"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * A small panel anchored under its trigger: enough for a short definition, no Radix
 * dependency, the same reasoning as `Dialog`. It is not modal. Escape and a click anywhere
 * outside close it, and nothing behind it is locked.
 *
 * The panel is positioned in CSS, under the trigger, which is all a one-paragraph popover
 * needs. Anything longer belongs in a `Dialog`.
 */
export function Popover({
  trigger,
  label,
  children,
  className,
}: {
  /** The content of the button that opens it. */
  trigger: ReactNode;
  /** The button's accessible name, since the trigger is usually an icon. */
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLSpanElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={root} className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((previous) => !previous)}
        className="inline-flex items-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {trigger}
      </button>
      {open ? (
        <span
          id={panelId}
          role="note"
          className={cn(
            "absolute left-0 top-full z-30 mt-1.5 block w-72 max-w-[80vw] rounded-md border bg-card p-3 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-card-foreground shadow-md",
            className,
          )}
        >
          {children}
        </span>
      ) : null}
    </span>
  );
}
