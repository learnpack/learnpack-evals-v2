"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { AssessorResponse, Uuid } from "@/lib/api/types";

/**
 * Who to give a course to, ticked one by one.
 *
 * A list rather than a `<select>`, and that is the whole reason it exists: the decision needs
 * three facts about a person at once — what they know, how much this campaign already asked of
 * them, and whether they are already on this course — and a native `<option>` takes no markup
 * and no width of its own. It used to take the expertise profile alone, truncated.
 *
 * **Ordered by current load, lightest first.** The question being answered is who has room, so
 * the answer goes at the top; registration order answered nothing.
 *
 * Somebody already assigned to the course is **disabled with the reason, never hidden**
 * (ADR-0028): it is the conflict the server would return, said before it is provoked. Somebody
 * over the ceiling is hidden — that is a filter the reader set and can unset — and the count of
 * who it hid is always shown, because a silent absence reads as a bug.
 */
export function EvaluatorPicker({
  evaluators,
  loadOf,
  alreadyAssigned,
  selected,
  onToggle,
  ceiling,
  onCeilingChange,
}: {
  evaluators: AssessorResponse[];
  /** How many seats this campaign has already given each of them. */
  loadOf: (assessorId: Uuid) => number;
  /** Who is on the chosen course already. Empty while no course is chosen. */
  alreadyAssigned: Set<Uuid>;
  selected: Uuid[];
  onToggle: (assessorId: Uuid) => void;
  /** Hide anybody at or over this many assignments. Empty string means no ceiling. */
  ceiling: string;
  onCeilingChange: (value: string) => void;
}) {
  const [filter, setFilter] = useState("");

  const ranked = useMemo(
    () =>
      [...evaluators].sort(
        (a, b) =>
          loadOf(a.assessor_id) - loadOf(b.assessor_id) ||
          (a.display_name ?? a.email ?? "").localeCompare(b.display_name ?? b.email ?? ""),
      ),
    [evaluators, loadOf],
  );

  const limit = ceiling.trim() === "" ? null : Number(ceiling);
  const overCeiling = useMemo(
    () =>
      limit === null || Number.isNaN(limit)
        ? []
        : ranked.filter(
            // Never the ones already ticked: hiding a choice the reader just made would
            // silently unmake it as far as they can tell.
            (a) => loadOf(a.assessor_id) >= limit && !selected.includes(a.assessor_id),
          ),
    [ranked, limit, loadOf, selected],
  );

  const shown = useMemo(() => {
    const hidden = new Set(overCeiling.map((a) => a.assessor_id));
    const needle = filter.trim().toLowerCase();
    return ranked.filter((a) => {
      if (hidden.has(a.assessor_id)) return false;
      if (!needle) return true;
      return `${a.display_name ?? ""} ${a.email ?? ""} ${a.expertise ?? ""}`
        .toLowerCase()
        .includes(needle);
    });
  }, [ranked, overCeiling, filter]);

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name or expertise…"
          aria-label="Filter evaluators"
        />
        <div className="flex shrink-0 items-center gap-1.5">
          <Label htmlFor="evaluator-ceiling" className="whitespace-nowrap text-xs font-normal">
            Hide from
          </Label>
          <Input
            id="evaluator-ceiling"
            type="number"
            min={1}
            value={ceiling}
            onChange={(e) => onCeilingChange(e.target.value)}
            className="w-16"
            aria-label="Hide evaluators with this many assignments or more"
          />
        </div>
      </div>

      <div className="max-h-64 space-y-1 overflow-y-auto rounded-md border p-2">
        {shown.length === 0 ? (
          <p className="px-2 py-3 text-sm text-muted-foreground">
            No evaluator is left to show. Widen the filter or raise the ceiling.
          </p>
        ) : (
          shown.map((a) => {
            const taken = alreadyAssigned.has(a.assessor_id);
            const name = a.display_name ?? a.email ?? a.assessor_id.slice(0, 8);
            return (
              <label
                key={a.assessor_id}
                className={
                  taken
                    ? "flex items-start gap-2 rounded px-2 py-1.5 text-sm opacity-60"
                    : "flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                }
              >
                <input
                  type="checkbox"
                  checked={selected.includes(a.assessor_id)}
                  disabled={taken}
                  onChange={() => onToggle(a.assessor_id)}
                  className="mt-0.5 h-4 w-4"
                />
                <span className="min-w-0">
                  <span className="font-medium">{name}</span>{" "}
                  <span className="text-xs text-muted-foreground">
                    · {loadOf(a.assessor_id)} assigned
                    {taken ? " · already on this course" : ""}
                  </span>
                  {a.expertise ? (
                    <span className="block text-xs text-muted-foreground">{a.expertise}</span>
                  ) : null}
                </span>
              </label>
            );
          })
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        {selected.length} selected of {evaluators.length} active
        {overCeiling.length > 0
          ? ` · ${overCeiling.length} hidden at ${limit}+ assignments`
          : ""}
        {filter.trim() ? ` · ${shown.length} shown` : ""}
      </p>
    </div>
  );
}
