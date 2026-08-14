import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { CriterionOutcomeState, OutcomeTally } from "@/lib/api/types";

/** One palette for the six states a criterion can end in.
 *
 *  `execution_error` is violet and not red on purpose (ADR-0037): it is a malfunction of
 *  the run, never a verdict about the course, and a reader who mistakes one for the other
 *  blames the generator for the platform's bad night.
 *
 *  Exhaustive by type — a seventh state does not compile until somebody gives it a colour. */
const OUTCOME_VARIANT: Record<CriterionOutcomeState, BadgeProps["variant"]> = {
  pass: "success",
  fail: "destructive",
  no_evidence: "warning",
  not_applicable: "outline",
  not_assessed: "secondary",
  execution_error: "malfunction",
};

/** The same six, spelled for a person rather than for a database column. */
const OUTCOME_LABEL: Record<CriterionOutcomeState, string> = {
  pass: "pass",
  fail: "fail",
  no_evidence: "no evidence",
  not_applicable: "not applicable",
  not_assessed: "not assessed",
  execution_error: "run failed",
};

export function OutcomeBadge({ outcome }: { outcome: CriterionOutcomeState }) {
  return <Badge variant={OUTCOME_VARIANT[outcome]}>{OUTCOME_LABEL[outcome]}</Badge>;
}

/** Read order for the state spelling, so a partition always reads the same way. */
export const OUTCOME_ORDER: readonly CriterionOutcomeState[] = [
  "pass",
  "fail",
  "no_evidence",
  "not_applicable",
  "not_assessed",
  "execution_error",
];

/** The same six states in their camelCase tally spelling, which is how the distributions
 *  count them. Two spellings of one vocabulary is not ideal, but they name two different
 *  things — a state and a count of it — and a third spelling would not help. */
export const TALLY_VARIANT: Record<OutcomeTally, BadgeProps["variant"]> = {
  pass: "success",
  fail: "destructive",
  noEvidence: "warning",
  notApplicable: "outline",
  notAssessed: "secondary",
  executionError: "malfunction",
};

export const TALLY_LABEL: Record<OutcomeTally, string> = {
  pass: "pass",
  fail: "fail",
  noEvidence: "no evidence",
  notApplicable: "not applicable",
  notAssessed: "not assessed",
  executionError: "run failed",
};

/** Read order, so a partition always reads the same way: what worked, what did not, then
 *  the three kinds of "nobody answered", then the one kind of "the run broke". */
export const TALLY_ORDER: readonly OutcomeTally[] = [
  "pass",
  "fail",
  "noEvidence",
  "notApplicable",
  "notAssessed",
  "executionError",
];
