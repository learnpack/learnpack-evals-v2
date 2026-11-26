"use client";

import { ChevronDown, ChevronRight, CornerLeftUp } from "lucide-react";
import type { SourceRootResponse } from "@/lib/api/types";

/**
 * Where the reader is inside a declared source root, each segment a step back up.
 *
 * Given the roots and `onRootChange`, and when more than one root is declared, the first
 * segment is where another root is chosen: the place the reader is already looking at when
 * they wonder where the courses are. Choosing one starts at its top. A select cannot be
 * clicked to go back to the top of the root it shows, so an *Up* button does that walk.
 */
export function FolderBreadcrumb({
  root,
  path,
  onNavigate,
  roots,
  onRootChange,
}: {
  root: string;
  path: string;
  onNavigate: (path: string) => void;
  roots?: SourceRootResponse[];
  onRootChange?: (root: string) => void;
}) {
  const segments = path ? path.split("/") : [];
  const choosable = onRootChange !== undefined && (roots?.length ?? 0) > 1;
  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      {choosable ? (
        <>
          {segments.length > 0 ? (
            <button
              type="button"
              aria-label="Up one folder"
              title="Up one folder"
              onClick={() => onNavigate(segments.slice(0, -1).join("/"))}
              className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <CornerLeftUp className="h-3.5 w-3.5" />
            </button>
          ) : null}
          <span className="relative inline-flex">
            <select
              aria-label="Source root"
              value={root}
              onChange={(event) => onRootChange(event.target.value)}
              className="appearance-none rounded border bg-background py-0.5 pl-1.5 pr-6 font-medium hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {roots!.map((source) => (
                <option key={source.key} value={source.key} disabled={!source.exists}>
                  {source.key}
                  {source.exists ? "" : " (missing on disk)"}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 opacity-60" />
          </span>
        </>
      ) : (
        <button
          type="button"
          onClick={() => onNavigate("")}
          className="rounded px-1.5 py-0.5 font-medium hover:bg-accent"
        >
          {root}
        </button>
      )}
      {segments.map((segment, index) => (
        <span key={segment + index} className="flex items-center gap-1">
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          <button
            type="button"
            onClick={() => onNavigate(segments.slice(0, index + 1).join("/"))}
            className="rounded px-1.5 py-0.5 hover:bg-accent"
          >
            {segment}
          </button>
        </span>
      ))}
    </div>
  );
}
