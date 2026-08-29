import type {
  ContentResponse,
  DatasetResponse,
  DatasetVersionResponse,
  Uuid,
} from "@/lib/api/types";

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

export type MembershipSummary = {
  total: number;
  /** Cannot be handed to a human evaluator: no deployed instance is declared (ADR-0028). */
  undeployed: number;
  /** Cannot enter a brief-paired dataset: the commission is the pairing key (ADR-0039). */
  withoutBrief: number;
  /** How many distinct generator versions the set spans — what a reference set exists to mix. */
  generatorVersions: number;
  withoutGenerator: number;
  /** More than one means members whose declared data differs, so different items are asked
   *  of an evaluator (ADR-0053). */
  formats: string[];
};

/**
 * What a version's membership is made of — the facts that decide whether it is fit to put in
 * front of people.
 *
 * **Returns `null` until the courses have loaded**, and that is the reason it lives here
 * rather than in the component: a summary computed over a half-loaded list would report "0
 * not deployed" where it means "not known yet", which is the one thing a readiness line must
 * never do.
 */
export function summarizeMembership(
  contentIds: Uuid[],
  contents: ContentResponse[] | undefined,
): MembershipSummary | null {
  if (!contents) return null;

  const byId = new Map(contents.map((course) => [course.content_id, course]));
  const members = contentIds.map((id) => byId.get(id)).filter((c) => c !== undefined);

  return {
    total: contentIds.length,
    undeployed: members.filter((course) => !course.consumable_url).length,
    withoutBrief: members.filter((course) => course.brief_id === null).length,
    generatorVersions: new Set(
      members.map((course) => course.generator_version_id).filter((id) => id !== null),
    ).size,
    withoutGenerator: members.filter((course) => course.generator_version_id === null).length,
    formats: [...new Set(members.map((course) => course.package_format))].sort(),
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
