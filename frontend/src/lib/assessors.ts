/** Who can be given a course to read.
 *
 * Two axes, and both have to be asked (GLOSSARY, ADR-0016). `role` is what somebody may do in
 * the console; `kind` is what kind of assessor they are — a person or an artifact. An
 * automated assessor is registered with neither role nor status stated, so it takes the
 * defaults every assessor takes, `evaluator` and `active`. Asking about the role alone
 * therefore answers "yes" for every instrument package in the store.
 *
 * They are not interchangeable: an automated assessor never signs in, never opens a course and
 * never answers a reference instrument. It is judged by the study that runs it, not asked.
 */

import type { AssessorResponse } from "@/lib/api/types";

export function isAssignableEvaluator(assessor: AssessorResponse): boolean {
  return (
    assessor.kind === "human" && assessor.role === "evaluator" && assessor.status === "active"
  );
}
