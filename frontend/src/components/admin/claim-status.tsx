import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { ClaimStatus } from "@/lib/api/types";

/** One palette for the three states a claim can be in.
 *
 *  It settles a real disagreement: the calibration page painted `supported` green and
 *  `insufficient` amber, while the report painted them primary and grey. Same three words,
 *  two colour schemes, adjacent pages — and the reader who noticed would have been right to
 *  stop trusting either. Calibration's reading wins, because it distinguishes the case that
 *  matters: `insufficient` is not a mild verdict, it is the absence of one, and amber says
 *  "nobody answered this" where grey says "answered, quietly".
 *
 *  Exhaustive by type — a fourth status does not compile until somebody gives it a colour. */
const CLAIM_STATUS_VARIANT: Record<ClaimStatus, BadgeProps["variant"]> = {
  supported: "success",
  refuted: "destructive",
  insufficient: "warning",
};

export function ClaimStatusBadge({
  status,
  children,
}: {
  status: ClaimStatus;
  children?: React.ReactNode;
}) {
  return <Badge variant={CLAIM_STATUS_VARIANT[status]}>{children ?? status}</Badge>;
}

export function claimStatusVariant(status: ClaimStatus): BadgeProps["variant"] {
  return CLAIM_STATUS_VARIANT[status];
}
