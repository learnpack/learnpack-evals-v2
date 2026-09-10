"use client";

import { useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { EmptyState, LoadingState } from "@/components/ui/states";
import { ReadinessLine } from "@/components/admin/readiness-line";
import { useGeneratorVersions } from "@/lib/api/hooks";
import type { ContentResponse, GeneratorVersionResponse, Uuid } from "@/lib/api/types";
import { courseLabel, courseRef } from "@/lib/courses";
import { summarizeMembership } from "@/lib/datasets";
import { cn } from "@/lib/utils";
import { groupByVersion, UNKNOWN_VERSION } from "@/lib/versions";

/** Both lists, the same box: tall enough to read a set by, and never taller than a window. */
const LIST_BOX = "h-[60vh] min-h-72 min-w-0 overflow-y-auto rounded-md border p-2";

/** How a course differs from the version being edited, in the console's soft palette: an
 *  accent border over a faint fill. Leaving the set is amber, not red — red here means that
 *  something failed, and taking a course out is a change the note explains, not an error. */
const ADDED_BADGE =
  "shrink-0 border-emerald-600/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
const REMOVED_BADGE =
  "shrink-0 border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-400";

/** The generator filter's "no filter" value — distinct from `UNKNOWN_VERSION`, which filters
 *  *to* the courses that declare no generator. */
const ALL_VERSIONS = "";

/** The membership a version form starts from, so each course can say how it differs. */
export type PickerBaseline = { contentIds: Uuid[]; ordinal: number };

const generatorKey = (course: ContentResponse) => course.generator_version_id ?? UNKNOWN_VERSION;

const byName = (a: ContentResponse, b: ContentResponse) =>
  courseLabel(a).localeCompare(courseLabel(b));

/**
 * A generator version as it is named everywhere, "<lineage> <version>".
 *
 * No resolved version means two different things — the declared void of ADR-0024, or a
 * version whose list has not loaded yet — and they must never read the same, for the reason
 * `summarizeMembership` gives: "unknown" where the truth is "not known yet" is a false fact.
 */
function generatorName(key: string, version: GeneratorVersionResponse | null | undefined): string {
  if (version) return `${version.name} ${version.version}`;
  return key === UNKNOWN_VERSION ? "Unknown generator" : "Generator …";
}

/** What the available list shows: both filters at once, each ignored while it is empty. */
function matchesFilter(course: ContentResponse, text: string, versionKey: string): boolean {
  if (versionKey !== ALL_VERSIONS && generatorKey(course) !== versionKey) return false;
  const needle = text.trim().toLowerCase();
  if (!needle) return true;
  // Both, because both are typed: the name is what somebody remembers a course by, the
  // external id is what they paste out of a spreadsheet (ADR-0059 §2).
  return `${course.title ?? ""} ${course.external_id}`.toLowerCase().includes(needle);
}

/**
 * The courses a set is made of, composed across two lists.
 *
 * **The set is never filtered.** "In this set" always shows the whole membership, grouped by
 * the generator version that made it; the filters only narrow what is still available. A
 * filter over a single list would hide members, and a set whose members can be out of sight
 * is a set someone freezes without having read it.
 *
 * Filtering is an aid to picking, not a rule the set keeps: what is frozen is the list of
 * courses, enumerated by a person (ADR-0058 §7). A set that follows a generator version on
 * its own would be a recipe — and that is a study's `GeneratorScope`, not a dataset.
 *
 * Shared by both dataset forms because they pick from the same population and a second copy
 * would drift — the declaring form starts empty, the version form starts from the current
 * membership and passes it as `baseline`, and that is the only difference between them.
 *
 * A course with no deployed instance is **marked, never hidden** (ADR-0028): it is still an
 * evaluand for the automated path, and what it cannot take is a human assignment — a refusal
 * that belongs where the assignment is made, not here.
 */
export function CoursePicker({
  courses,
  selected,
  onChange,
  baseline,
}: {
  courses: ContentResponse[] | undefined;
  selected: Uuid[];
  onChange: (next: Uuid[]) => void;
  baseline?: PickerBaseline;
}) {
  const { data: generatorVersions } = useGeneratorVersions();
  const [text, setText] = useState("");
  const [versionKey, setVersionKey] = useState(ALL_VERSIONS);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const baselineIds = baseline?.contentIds;
  const baselineSet = useMemo(() => (baselineIds ? new Set(baselineIds) : null), [baselineIds]);
  const versionById = useMemo(
    () => new Map((generatorVersions ?? []).map((v) => [v.generator_version_id, v])),
    [generatorVersions],
  );

  const chosenGroups = useMemo(
    () =>
      groupByVersion(
        (courses ?? []).filter((course) => selectedSet.has(course.content_id)),
        generatorVersions ?? [],
      ),
    [courses, generatorVersions, selectedSet],
  );
  // Not expected — content is never retired (ADR-0033) — but a member the list cannot resolve
  // is still a member, and this list exists so that no member is ever out of sight.
  const unresolved = useMemo(() => {
    const known = new Set((courses ?? []).map((course) => course.content_id));
    return selected.filter((id) => !known.has(id));
  }, [courses, selected]);

  const available = useMemo(
    () => (courses ?? []).filter((course) => !selectedSet.has(course.content_id)).sort(byName),
    [courses, selectedSet],
  );
  const shown = useMemo(
    () => available.filter((course) => matchesFilter(course, text, versionKey)),
    [available, text, versionKey],
  );
  // Offered over every registered course, not only the available ones: a version whose
  // courses are all in the set still exists, and its option saying "0 available" is the fact.
  const versionOptions = useMemo(
    () =>
      groupByVersion(courses ?? [], generatorVersions ?? []).map((group) => ({
        key: group.key,
        name: generatorName(group.key, group.version),
        available: group.courses.filter((course) => !selectedSet.has(course.content_id)).length,
      })),
    [courses, generatorVersions, selectedSet],
  );

  if (!courses) return <LoadingState />;
  if (courses.length === 0) {
    return <EmptyState title="No courses" hint="Register a course first." />;
  }

  const summary = summarizeMembership(selected, courses);
  const filtering = Boolean(text.trim()) || versionKey !== ALL_VERSIONS;

  const add = (ids: Uuid[]) => onChange([...selected, ...ids.filter((id) => !selectedSet.has(id))]);
  const remove = (ids: Uuid[]) => {
    const dropped = new Set(ids);
    onChange(selected.filter((id) => !dropped.has(id)));
  };

  // One grid of eight cells rather than two columns of four: each row is as tall as its
  // taller cell, so the two lists start and end together whatever sits above or below them.
  // When the columns collapse, `order` restacks the cells into two whole areas, the set
  // first — it is the one that must never be out of sight.
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
      <h3 className="order-1 text-sm font-medium md:order-none">In this set</h3>
      <h3 className="order-5 mt-4 text-sm font-medium md:order-none md:mt-0">Available</h3>

      <div className="order-2 flex min-h-10 min-w-0 items-center md:order-none">
        {summary ? <ReadinessLine summary={summary} /> : null}
      </div>
      <div className="order-6 grid min-w-0 gap-2 sm:grid-cols-2 md:order-none">
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          // The picker sits inside a form: Enter here means "done typing", never "freeze
          // the set".
          onKeyDown={(e) => {
            if (e.key === "Enter") e.preventDefault();
          }}
          placeholder="Filter by course…"
          aria-label="Filter available courses by name"
        />
        <Select
          value={versionKey}
          onChange={(e) => setVersionKey(e.target.value)}
          aria-label="Filter available courses by generator version"
        >
          <option value={ALL_VERSIONS}>All generator versions</option>
          {versionOptions.map((option) => (
            <option key={option.key} value={option.key}>
              {option.name} · {option.available} available
            </option>
          ))}
        </Select>
      </div>

      <div
        role="region"
        aria-label="Courses in this set"
        className={cn(LIST_BOX, "order-3 space-y-3 md:order-none")}
      >
        {selected.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">
            Nothing in this set yet — add courses from the list.
          </p>
        ) : (
          <>
            {chosenGroups.map((group) => (
              <MemberGroup
                key={group.key}
                title={`${generatorName(group.key, group.version)} · ${group.courses.length}`}
                onRemoveAll={() => remove(group.courses.map((course) => course.content_id))}
              >
                {[...group.courses].sort(byName).map((course) => (
                  <MemberRow
                    key={course.content_id}
                    label={courseLabel(course)}
                    detail={`v${course.version}${course.consumable_url ? "" : " · not deployed"}`}
                    isNew={baselineSet !== null && !baselineSet.has(course.content_id)}
                    onRemove={() => remove([course.content_id])}
                  />
                ))}
              </MemberGroup>
            ))}
            {unresolved.length ? (
              <MemberGroup
                title={`Not in the course list · ${unresolved.length}`}
                onRemoveAll={() => remove(unresolved)}
              >
                {unresolved.map((id) => (
                  <MemberRow
                    key={id}
                    label={`Course ${courseRef(id)}`}
                    detail={null}
                    isNew={false}
                    onRemove={() => remove([id])}
                  />
                ))}
              </MemberGroup>
            ) : null}
          </>
        )}
      </div>
      <div
        role="region"
        aria-label="Available courses"
        className={cn(LIST_BOX, "order-7 space-y-1 md:order-none")}
      >
        {available.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">
            Every registered course is in this set.
          </p>
        ) : shown.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">
            No available course matches the filter.
          </p>
        ) : (
          shown.map((course) => {
            const key = generatorKey(course);
            return (
              <button
                key={course.content_id}
                type="button"
                onClick={() => add([course.content_id])}
                aria-label={`Add ${courseLabel(course)}`}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-accent"
              >
                <Plus className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  {courseLabel(course)}{" "}
                  <span className="text-xs text-muted-foreground">
                    · v{course.version} · {generatorName(key, versionById.get(key))}
                    {course.consumable_url ? null : " · not deployed"}
                  </span>
                </span>
                {/* It was a member of the version this one starts from: taking it out is
                    part of the change being recorded. */}
                {baselineSet?.has(course.content_id) ? (
                  <Badge variant="outline" className={REMOVED_BADGE}>
                    in v{baseline?.ordinal}
                  </Badge>
                ) : null}
              </button>
            );
          })
        )}
      </div>

      <p className="order-4 flex min-h-9 items-center text-xs text-muted-foreground md:order-none">
        Grouped by the generator version that made them.
      </p>
      <div className="order-8 flex min-h-9 flex-wrap items-center justify-between gap-2 md:order-none">
        <p className="text-xs text-muted-foreground">
          {available.length} available{filtering ? ` · ${shown.length} shown` : ""}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={shown.length === 0}
          onClick={() => add(shown.map((course) => course.content_id))}
        >
          <Plus className="h-3.5 w-3.5" /> Add all {shown.length} shown
        </Button>
      </div>
    </div>
  );
}

/** One generator version's members, with the act that undoes an "Add all shown" whole. */
function MemberGroup({
  title,
  onRemoveAll,
  children,
}: {
  title: string;
  onRemoveAll: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-2 px-2 pb-1">
        <span className="text-xs font-medium text-muted-foreground">{title}</span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs"
          onClick={onRemoveAll}
        >
          Remove all
        </Button>
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

/** Add or remove one id. The picker moves ids in bulk now; the assignment form still ticks
 *  them one at a time. */
export function toggleIn(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((id) => id !== value) : [...list, value];
}

function MemberRow({
  label,
  detail,
  isNew,
  onRemove,
}: {
  label: string;
  detail: string | null;
  /** Not in the version this one starts from — part of the change being recorded. */
  isNew: boolean;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent">
      <span className="min-w-0 flex-1">
        {label}{" "}
        {detail ? <span className="text-xs text-muted-foreground">· {detail}</span> : null}
      </span>
      {isNew ? (
        <Badge variant="outline" className={ADDED_BADGE}>
          new
        </Badge>
      ) : null}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label}`}
        className="shrink-0 rounded p-1 text-muted-foreground hover:bg-background hover:text-foreground"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
