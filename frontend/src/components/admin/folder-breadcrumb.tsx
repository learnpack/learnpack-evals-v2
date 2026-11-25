"use client";

import { ChevronRight } from "lucide-react";

/** Where the reader is inside a declared source root, each segment a step back up. */
export function FolderBreadcrumb({
  root,
  path,
  onNavigate,
}: {
  root: string;
  path: string;
  onNavigate: (path: string) => void;
}) {
  const segments = path ? path.split("/") : [];
  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <button
        type="button"
        onClick={() => onNavigate("")}
        className="rounded px-1.5 py-0.5 font-medium hover:bg-accent"
      >
        {root}
      </button>
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
