import type {
  ContentResponse,
  GeneratorVersionResponse,
  StudyResponse,
  Uuid,
} from "@/lib/api/types";

/** The declared void of ADR-0024 as a group key: courses that name no generator. */
export const UNKNOWN_VERSION = "unknown";

/** One generator version and everything registered against it. `version: null` is the
 *  declared void — a group, but never something a round can measure. */
export type VersionGroup = {
  /** The version id, or `unknown`. Doubles as the value a study link carries. */
  key: string;
  version: GeneratorVersionResponse | null;
  courses: ContentResponse[];
  /** The commissions it answered. A course with no brief is counted apart, not as one. */
  briefIds: Set<Uuid>;
  withoutBrief: number;
  formats: string[];
};

/**
 * The registered courses read by the version that made them — the grain a round measures.
 *
 * Shared rather than local to one screen: the course list groups by it and the home asks it
 * what a version brought, and two definitions of "a version's commissions" would come to
 * disagree without anyone noticing which was right.
 */
export function groupByVersion(
  contents: ContentResponse[],
  generatorVersions: GeneratorVersionResponse[],
): VersionGroup[] {
  const byKey = new Map<string, ContentResponse[]>();
  for (const content of contents) {
    const key = content.generator_version_id ?? UNKNOWN_VERSION;
    byKey.set(key, [...(byKey.get(key) ?? []), content]);
  }

  const groups = [...byKey].map(([key, courses]) => ({
    key,
    version: generatorVersions.find((version) => version.generator_version_id === key) ?? null,
    courses,
    briefIds: new Set(
      courses.map((course) => course.brief_id).filter((id): id is Uuid => id !== null),
    ),
    withoutBrief: courses.filter((course) => course.brief_id === null).length,
    formats: [...new Set(courses.map((course) => course.package_format))].sort(),
  }));

  // Lineage, then version — the same `localeCompare` the rest of the console uses, with the
  // same known flaw (2.0.10 sorts before 2.0.9). Unknown last: it is not a version.
  return groups.sort((a, b) => {
    if (!a.version) return 1;
    if (!b.version) return -1;
    return (
      a.version.name.localeCompare(b.version.name) ||
      a.version.version.localeCompare(b.version.version)
    );
  });
}

export function sharedCommissions(a: VersionGroup, b: VersionGroup): number {
  let shared = 0;
  for (const briefId of a.briefIds) if (b.briefIds.has(briefId)) shared += 1;
  return shared;
}

/**
 * Every generator version some round has actually measured.
 *
 * Two ways a study names them, because a recipe has two forms (ADR-0044): a listed scope
 * says its versions itself; `"all"` can only be read off the courses the round materialized.
 *
 * **Drafts do not count.** A study that was never opened measured nothing, and its recipe
 * can still change entirely — counting it would hide the very version somebody still has to
 * measure, which is the one question this answers.
 */
export function measuredVersionIds(
  studies: StudyResponse[],
  contents: ContentResponse[],
): Set<Uuid> {
  const versionOfContent = new Map(
    contents.map((content) => [content.content_id, content.generator_version_id]),
  );
  const measured = new Set<Uuid>();

  for (const study of studies) {
    if (study.status !== "open" && study.status !== "signed_off") continue;
    if (Array.isArray(study.generator_scope)) {
      for (const id of study.generator_scope) measured.add(id);
      continue;
    }
    if (study.generator_scope === "all") {
      for (const contentId of study.content_ids) {
        const versionId = versionOfContent.get(contentId);
        if (versionId) measured.add(versionId);
      }
    }
  }
  return measured;
}
