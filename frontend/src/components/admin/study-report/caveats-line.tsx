"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { caveatRows } from "@/components/admin/study-report/rollup";
import { cn } from "@/lib/utils";
import type { ReportBody } from "@/lib/api/types";

/** Every caveat kind, behind one line.
 *
 *  Signing off with caveats is legitimate and visible; doing it silently is impossible
 *  (12-define invariant 4) — so none of them may be dropped. But a column of always-open
 *  rows mostly reading "none" is how a reader learns to skip the section that exists to stop
 *  them skipping it. One line says how many fired; opening it shows every kind, fired or
 *  not, because "we checked and there was none" is information too.
 *
 *  The summary counts `rows`, never a number written into the sentence: the kinds have grown
 *  twice now, and a hardcoded "eight" is a claim that goes quietly false. */
export function CaveatsLine({ body }: { body: ReportBody }) {
  const [open, setOpen] = useState(false);
  const rows = caveatRows(body);
  const raised = rows.filter((row) => row.raised);

  return (
    <div className="rounded-lg border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm hover:bg-accent/40"
      >
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
            !open && "-rotate-90",
          )}
        />
        <span className="font-medium">Caveats</span>
        {raised.length > 0 ? (
          <Badge variant="warning">{raised.length} raised</Badge>
        ) : (
          <Badge variant="success">none raised</Badge>
        )}
        <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
          {raised.length > 0
            ? raised.map((row) => row.label.toLowerCase()).join(" · ")
            : `all ${rows.length} kinds checked`}
        </span>
      </button>
      {open ? (
        <dl className="space-y-2 border-t px-4 py-3 text-sm">
          {rows.map((row) => (
            <div key={row.key} className="flex flex-wrap gap-x-2">
              <dt className={cn("font-medium", !row.raised && "text-muted-foreground")}>
                {row.label}:
              </dt>
              <dd className={cn("text-muted-foreground", row.raised && "text-foreground")}>
                {row.detail}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
