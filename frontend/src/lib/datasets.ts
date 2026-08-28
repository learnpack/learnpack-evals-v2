import type { DatasetResponse, DatasetVersionResponse, Uuid } from "@/lib/api/types";

/**
 * Set math over a dataset's version line (ADR-0058).
 *
 * Pure functions in `lib/` rather than inside a component, for the reason `lib/versions.ts`
 * gives: two definitions of "what changed between these versions" would come to disagree
 * without anyone noticing which was right.
 */

export type MembershipDiff = {
  added: Uuid[];
  removed: Uuid[];
};

/** The version a campaign gets when nobody names one. `null` cannot happen for a stored
 *  dataset — declaring one freezes v1 — but the list is data off the wire, so it is read
 *  defensively rather than indexed into. */
export function latestVersion(dataset: DatasetResponse): DatasetVersionResponse | null {
  return dataset.versions.length ? dataset.versions[dataset.versions.length - 1] : null;
}

/** What entered and what left, between a version and the one before it.
 *
 * `previous` is absent for v1, and then everything is an addition rather than an unknown —
 * a first version is a set arriving, not a set changing. */
export function diffMembership(
  previous: DatasetVersionResponse | null,
  current: DatasetVersionResponse,
): MembershipDiff {
  const was = new Set(previous?.content_ids ?? []);
  const now = new Set(current.content_ids);
  return {
    added: current.content_ids.filter((id) => !was.has(id)),
    removed: [...was].filter((id) => !now.has(id)),
  };
}

/** The line read the way a reader reads it — newest first — each version paired with the
 *  diff that produced it. */
export function versionHistory(
  dataset: DatasetResponse,
): { version: DatasetVersionResponse; diff: MembershipDiff }[] {
  return dataset.versions
    .map((version, index) => ({
      version,
      diff: diffMembership(index === 0 ? null : dataset.versions[index - 1], version),
    }))
    .reverse();
}
