import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { StudyStatus } from "@/lib/api/types";

/** One palette for the study's four states, shared by the list and the study's own page:
 *  two pages showing one study in two colours is how a reader stops trusting either.
 *
 *  Exhaustive by type — a fifth status does not compile until somebody gives it a colour,
 *  which is the whole safety net in a frontend with no tests. `published` takes the
 *  `success` the calibration page settled on for a good outcome that is over, instead of
 *  sharing `default` with `open` as it did: those two are the states the reader most needs
 *  to tell apart, since only one of them still accepts work. */
const STUDY_STATUS_VARIANT: Record<StudyStatus, BadgeProps["variant"]> = {
  declared: "outline",
  prepared: "secondary",
  open: "default",
  published: "success",
};

export function StudyStatusBadge({ status }: { status: StudyStatus }) {
  return <Badge variant={STUDY_STATUS_VARIANT[status]}>{status}</Badge>;
}
