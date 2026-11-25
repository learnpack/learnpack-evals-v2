"use client";

import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Controlled tabs: a row of buttons and the one panel that is showing. No Radix, the same
 * reasoning as `Dialog`. The panels that are not showing are not rendered, so a tab that
 * fetches does so only when it is opened.
 *
 * Arrow keys, Home and End move between tabs, as the WAI-ARIA tabs pattern expects.
 */
export function Tabs<T extends string>({
  value,
  onChange,
  tabs,
  label,
  children,
}: {
  value: T;
  onChange: (value: T) => void;
  tabs: { value: T; label: ReactNode }[];
  label: string;
  children: ReactNode;
}) {
  const id = useId();
  const index = tabs.findIndex((tab) => tab.value === value);

  function go(at: number) {
    const next = tabs[(at + tabs.length) % tabs.length];
    onChange(next.value);
    document.getElementById(`${id}-${next.value}`)?.focus();
  }

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label={label}
        className="flex flex-wrap gap-1 border-b"
        onKeyDown={(event) => {
          if (event.key === "ArrowRight") go(index + 1);
          else if (event.key === "ArrowLeft") go(index - 1);
          else if (event.key === "Home") go(0);
          else if (event.key === "End") go(tabs.length - 1);
          else return;
          event.preventDefault();
        }}
      >
        {tabs.map((tab) => {
          const selected = tab.value === value;
          return (
            <button
              key={tab.value}
              id={`${id}-${tab.value}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`${id}-panel`}
              tabIndex={selected ? 0 : -1}
              onClick={() => onChange(tab.value)}
              className={cn(
                "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                selected
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${value}`}>
        {children}
      </div>
    </div>
  );
}
