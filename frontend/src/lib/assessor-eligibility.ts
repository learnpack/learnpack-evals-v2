import type { AssessorPackageResponse } from "@/lib/api/types";

/** The automated assessors that may judge with an instrument version: the ones ratified
 *  against it (ADR-0019), since an assessor that has not ratified would be refused by the
 *  endpoint, and an option that cannot work is worse than no option (ADR-0036). */
export function ratifiedFor(
  packages: AssessorPackageResponse[],
  instrumentVersionId: string,
): AssessorPackageResponse[] {
  if (!instrumentVersionId) return [];
  return packages.filter(
    (pkg) =>
      pkg.assessor_id !== null &&
      pkg.lineage_versions.some(
        (version) => version.instrument_version_id === instrumentVersionId && version.ratified,
      ),
  );
}
