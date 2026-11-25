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

/** What an assessor will decide on courses of one format: of the instrument's criteria, how
 *  many the format can supply the data for, and how many of those this assessor executes
 *  rather than abstains from. `null` while the format's matching is still loading, so "we do
 *  not know yet" never reads as "none". */
export function assessorReach(
  pkg: AssessorPackageResponse,
  matching: { criteria: { criterionId: string; missingData: string[] }[] } | undefined,
): { decides: number; supplied: number; total: number } | null {
  if (!matching) return null;
  const supplied = matching.criteria.filter((criterion) => criterion.missingData.length === 0);
  const executes = new Set(pkg.executes);
  return {
    decides: supplied.filter((criterion) => executes.has(criterion.criterionId)).length,
    supplied: supplied.length,
    total: matching.criteria.length,
  };
}
