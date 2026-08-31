"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/states";
import type { ContentResponse } from "@/lib/api/types";
import { courseLabel } from "@/lib/courses";
import { cn } from "@/lib/utils";

/**
 * The courses a set is made of, ticked one by one.
 *
 * Shared by both dataset forms because they pick from the same population and a second copy
 * would drift — the declaring form starts empty, the version form starts from the current
 * membership, and that is the only difference between them.
 *
 * A course with no deployed instance is **marked, never hidden** (ADR-0028): it is still an
 * evaluand for the automated path, and what it cannot take is a human assignment — a refusal
 * that belongs where the assignment is made, not here.
 */
export function CoursePicker({
  courses,
  selected,
  onToggle,
}: {
  courses: ContentResponse[] | undefined;
  selected: string[];
  onToggle: (contentId: string) => void;
}) {
  const [filter, setFilter] = useState("");

  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return courses ?? [];
    // Both, because both are typed: the name is what somebody remembers a course by, the
    // external id is what they paste out of a spreadsheet (ADR-0059 §2).
    return (courses ?? []).filter((course) =>
      `${course.title ?? ""} ${course.external_id}`.toLowerCase().includes(needle),
    );
  }, [courses, filter]);

  if (!courses || courses.length === 0) {
    return <EmptyState title="No courses" hint="Register a course first." />;
  }

  return (
    <div className="space-y-2">
      <Input
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter by course…"
        aria-label="Filter courses"
      />
      <div className="max-h-64 space-y-1 overflow-y-auto rounded-md border p-2">
        {shown.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">
            No course matches “{filter.trim()}”.
          </p>
        ) : (
          shown.map((course) => (
            <label
              key={course.content_id}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent",
              )}
            >
              <input
                type="checkbox"
                checked={selected.includes(course.content_id)}
                onChange={() => onToggle(course.content_id)}
                className="h-4 w-4"
              />
              {courseLabel(course)} · v{course.version}
              {course.consumable_url ? null : (
                <span className="text-xs text-muted-foreground">· not deployed</span>
              )}
            </label>
          ))
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        {selected.length} selected of {courses.length} registered
        {filter.trim() ? ` · ${shown.length} shown` : ""}
      </p>
    </div>
  );
}

/** Add or remove one id, the only mutation either form needs. */
export function toggleIn(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((id) => id !== value) : [...list, value];
}
