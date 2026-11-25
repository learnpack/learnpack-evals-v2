"use client";

import { useState } from "react";
import { ClaimStatusBadge } from "@/components/admin/claim-status";
import { OUTCOME_ORDER, OutcomeBadge } from "@/components/admin/outcome-badge";
import { Select } from "@/components/ui/select";
import type { ClaimStatus, CriterionOutcomeState } from "@/lib/api/types";

/**
 * Six states a criterion can end in, and the two places they are counted.
 *
 * The two readings are shown side by side on purpose, because they count differently and
 * mixing them up is the mistake this exists to prevent:
 *
 * - **The claim**, as the report reads it: supported iff every criterion passed, refuted iff
 *   any failed, insufficient otherwise, and left out only when every criterion is
 *   `not_applicable` (`evaluation/domain/judgment.py`, ADR-0018 §4). `not_assessed` stays in.
 * - **The optimization signal** (ADR-0023): pass / (pass + fail + no_evidence), with the
 *   other three states outside the arithmetic, and `undefined`, never 0, when nothing counts.
 *   It is a number to optimize a generator against, kept apart from the report (§11).
 *
 * The example claim and its three criteria are real; the outcomes are the reader's to set.
 */
const CRITERIA: { id: string; statement: string; initial: CriterionOutcomeState }[] = [
  {
    id: "cr-course-opens-with-general-intro",
    statement: "The course reserves its opening slot.",
    initial: "pass",
  },
  {
    id: "cr-course-has-development",
    statement: "The course has a development body.",
    initial: "pass",
  },
  {
    id: "cr-arc-character",
    statement: "The opening lesson introduces and the final lesson closes.",
    initial: "not_assessed",
  },
];

const MEANING: Record<CriterionOutcomeState, string> = {
  pass: "There is evidence, and it satisfies the criterion.",
  fail: "There is evidence, and it does not satisfy the criterion.",
  no_evidence: "The course could carry this, and does not.",
  not_applicable: "This course format cannot supply what the criterion needs.",
  not_assessed: "The assessor declares that it does not check this criterion.",
  execution_error: "The run failed on this criterion. A fact about the run, not the course.",
};

function claimStatus(outcomes: CriterionOutcomeState[]): ClaimStatus | "excluded" {
  if (outcomes.every((o) => o === "not_applicable")) return "excluded";
  if (outcomes.some((o) => o === "fail")) return "refuted";
  if (outcomes.every((o) => o === "pass")) return "supported";
  return "insufficient";
}

const CLAIM_READING: Record<ClaimStatus | "excluded", string> = {
  supported: "Every criterion passed.",
  refuted: "A criterion failed, and one cited counterexample is enough to refute the claim.",
  insufficient:
    "Nothing failed, but not every criterion passed, so there is no verdict. A criterion that was not assessed keeps the claim open; it does not count as a pass.",
  excluded: "No criterion applies to this format, so the claim is left out for this course.",
};

export function OutcomesCalculator() {
  const [outcomes, setOutcomes] = useState(CRITERIA.map((c) => c.initial));

  const status = claimStatus(outcomes);
  const pass = outcomes.filter((o) => o === "pass").length;
  const against = outcomes.filter((o) => o === "fail" || o === "no_evidence").length;
  const counted = pass + against;
  const left = outcomes.length - counted;

  return (
    <div className="space-y-4">
      <p className="text-sm">
        Claim: <em>The course follows the intended arc: a general introduction, thematic
        development and a closing.</em>
      </p>

      <div className="divide-y rounded-md border">
        {CRITERIA.map((criterion, index) => (
          <div
            key={criterion.id}
            className="grid gap-2 px-3 py-2.5 sm:grid-cols-[minmax(0,1fr)_11rem] sm:items-center"
          >
            <div className="min-w-0 text-sm">
              <p>{criterion.statement}</p>
              <p className="font-mono text-[11px] text-muted-foreground">{criterion.id}</p>
              <p className="mt-1 text-xs text-muted-foreground">{MEANING[outcomes[index]]}</p>
            </div>
            <Select
              id={`outcome-${criterion.id}`}
              aria-label={`Outcome of ${criterion.id}`}
              value={outcomes[index]}
              onChange={(event) =>
                setOutcomes((previous) =>
                  previous.map((value, at) =>
                    at === index ? (event.target.value as CriterionOutcomeState) : value,
                  ),
                )
              }
            >
              {OUTCOME_ORDER.map((outcome) => (
                <option key={outcome} value={outcome}>
                  {outcome.replace("_", " ")}
                </option>
              ))}
            </Select>
          </div>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2" aria-live="polite">
        <div className="space-y-2 rounded-md border p-3">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            In the report: the claim
          </p>
          <div>
            {status === "excluded" ? (
              <OutcomeBadge outcome="not_applicable" />
            ) : (
              <ClaimStatusBadge status={status} />
            )}
          </div>
          <p className="text-sm">{CLAIM_READING[status]}</p>
        </div>

        <div className="space-y-2 rounded-md border border-dashed p-3">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            In the optimization signal
          </p>
          <p className="font-mono text-2xl tabular-nums">
            {counted ? (pass / counted).toFixed(2) : "undefined"}
          </p>
          <p className="text-sm">
            {counted
              ? `${pass} pass out of ${counted} counted. ${left} left out: not applicable, not assessed and run failures are outside the arithmetic.`
              : "Nothing counted, so the value is undefined, never 0. Reading it as 0 would score the generator on questions nobody asked."}
          </p>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        The two disagree on purpose. The report keeps a criterion nobody assessed inside the
        claim, so the gap stays visible. The signal leaves it out, so a generator is not
        charged for what no assessor checks. Compare two signals only when they were computed
        over the same criteria, instrument version and assessor.
      </p>
    </div>
  );
}
