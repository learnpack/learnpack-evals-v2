import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * The acts of a long form, kept in reach: stuck to the bottom of the window while the form
 * scrolls under it, with the one line that says what submitting would record.
 *
 * The line lives here rather than above the buttons because it is read at the moment of
 * pressing them — a count that scrolled out of sight forty courses ago says nothing then.
 */
export function FormActions({
  status,
  warn = false,
  children,
}: {
  status: string;
  /** The status is a reason the act will be refused, not a description of it. */
  warn?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 border-t bg-background py-3">
      <p
        className={cn(
          "text-sm text-muted-foreground",
          warn && "text-amber-700 dark:text-amber-400",
        )}
      >
        {status}
      </p>
      <div className="flex gap-2">{children}</div>
    </div>
  );
}
