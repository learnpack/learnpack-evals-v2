import { Badge } from "@/components/ui/badge";
import type { ClaimValidity } from "@/lib/api/types";

/** How much to trust one claim's verdict, from the campaign the reader chose (ADR-0063).
 *
 *  It qualifies, it does not correct: the numbers beside it do not change, only how much they
 *  weigh. `unvalidated` is a measurement that did not conclude — the absence of any campaign
 *  shows nothing at all, which is why this renders `null` rather than a placeholder. */
export function ValidityBadge({ validity }: { validity: ClaimValidity | undefined }) {
  if (!validity) return null;

  const { label, variant } = READING[validity.status] ?? READING.unvalidated;
  return (
    <Badge variant={variant} title={explain(validity)}>
      {label}
    </Badge>
  );
}

const READING: Record<string, { label: string; variant: "success" | "warning" | "outline" }> = {
  tracks: { label: "tracks experts", variant: "success" },
  weak: { label: "weak validity", variant: "warning" },
  unvalidated: { label: "unvalidated", variant: "outline" },
};

/** The tooltip carries the why, because a badge that only grades invites the wrong fix: a
 *  claim nobody could measure is not a claim that measured badly. */
const WHY: Record<string, string> = {
  no_reference_item: "the reference instrument does not ask about this quality",
  too_few: "too few courses were judged by both sides",
  no_variance: "the panel only ever landed on one side, so there is nothing to separate",
  ceiling_too_low: "the two experts did not agree with each other, so there is nothing to match",
  sample_below_tracking: "measurable, but on too few courses to call it settled",
  kappa_below_bar: "agreement past chance is under the bar",
  degrades_from_ceiling: "it agrees with the panel far less often than the panel agrees with itself",
};

function explain(validity: ClaimValidity): string {
  const why = validity.reason ? (WHY[validity.reason] ?? validity.reason) : null;
  const measured =
    validity.sample > 0
      ? `${validity.sensitivity.hit}/${validity.sensitivity.of} of accepted, ` +
        `${validity.specificity.hit}/${validity.specificity.of} of rejected, ` +
        `over ${validity.sample} courses`
      : "nothing measured";
  return why ? `${why} — ${measured}` : measured;
}
