"use client";

import { use, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Maximize2, Minimize2 } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { ConsumeContent } from "@/components/evaluator/consume-content";
import { DeclaredData } from "@/components/evaluator/declared-data";
import { HowThisWorks } from "@/components/evaluator/how-this-works";
import { ScoreForm } from "@/components/evaluator/score-form";
import { useAssignment, useOpenAssignment, useSubmitEvaluation } from "@/lib/api/hooks";
import { assignedCourseLabel } from "@/lib/courses";
import { ApiError } from "@/lib/api/client";
import type { AssignmentDetail } from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * The evaluator's word for one of the things they are answering.
 *
 * A `likert` instrument asks for agreement with *statements* (ADR-0052 §3); the older
 * `numeric` shape asks *items*, and still resolves for a campaign pinned to rubric v1. It
 * follows the format rather than being written down once, because this word appears three
 * times on the screen and two of them are next to a count.
 */
function unitWord({ response_format }: AssignmentDetail, count = 2): string {
  const singular = response_format === "likert" ? "statement" : "item";
  return count === 1 ? singular : `${singular}s`;
}

/**
 * One working screen instead of a wizard: the course stays pinned on the left while the
 * evaluator scores on the right. Both right-hand panels start open and
 * can be collapsed; "Focus" hands the whole width to the course.
 */
export default function AssignmentPage({
  params,
}: {
  params: Promise<{ assignmentId: string }>;
}) {
  const { assignmentId } = use(params);
  const router = useRouter();
  const { data: assignment, isLoading, error } = useAssignment(assignmentId);
  const { mutate: markOpened } = useOpenAssignment();
  const submitEvaluation = useSubmitEvaluation();
  const [focus, setFocus] = useState(false);

  const alreadyDone = assignment?.status === "submitted" || assignment?.status === "cancelled";

  // Mark opened once the assignment is on screen (idempotent, best-effort — never blocks).
  const openedRef = useRef(false);
  useEffect(() => {
    if (!assignment || openedRef.current || alreadyDone) return;
    openedRef.current = true;
    markOpened(assignmentId);
  }, [assignment, alreadyDone, assignmentId, markOpened]);

  function handleSubmit(
    scores: { quality_id: string; score: number | null; comment: string | null }[],
  ) {
    submitEvaluation.mutate(
      { assignment_id: assignmentId, scores },
      {
        onSuccess: () => {
          toast.success("Review submitted. Thank you!");
          router.push("/evaluations");
        },
        onError: (err) => {
          const e = err as ApiError;
          if (e.status === 409) {
            toast.error("This assignment can no longer be submitted.", { description: e.message });
            router.push("/evaluations");
            return;
          }
          toast.error("Could not submit the evaluation.", { description: e.message });
        },
      },
    );
  }

  return (
    <>
      <AppHeader subtitle="Evaluator" />
      <main className="container py-6">
        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={(error as Error).message} />
        ) : !assignment ? (
          <ErrorState message="Assignment not found." />
        ) : alreadyDone ? (
          <Card className="mx-auto max-w-2xl">
            <CardContent className="py-10 text-center">
              {/* A sentence per state, rather than the stored word dropped into a template:
                  "This assignment is cancelled" is the model talking about itself. */}
              <p className="font-medium">
                {assignment.status === "submitted"
                  ? "You have already sent this review."
                  : "This review was cancelled."}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                There is nothing left to do here.
              </p>
              <Link href="/evaluations" className={cn(buttonVariants(), "mt-4")}>
                Back to your evaluations
              </Link>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <Link
                  href="/evaluations"
                  className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
                >
                  <ArrowLeft className="h-4 w-4" /> Back to your evaluations
                </Link>
                {/* The screen still says which course it is asking about (ADR-0059 §5) — it
                    just no longer says it twice. The course prints its own name at the top of
                    the frame, two centimetres below where this used to sit, so what is left
                    here is the part a rendered title cannot do: the page's heading, for
                    anybody navigating by structure, and the name for a reader who has no
                    frame to read it from. The two states where the course does not load carry
                    it themselves, in the message that names the problem. */}
                <h1 className="sr-only">
                  {assignedCourseLabel(assignment.content_title, assignment.content_id)}
                </h1>
              </div>
              <div className="flex items-center gap-2">
                {/* "Open in new tab" is not here: it is an action on the course, so it lives on
                    the course's own bar, and it opens the URL the session was minted into
                    rather than the plain one this page holds. */}
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={() => setFocus((v) => !v)}
                  aria-pressed={focus}
                  className="hidden lg:inline-flex"
                >
                  {focus ? (
                    <>
                      <Minimize2 className="h-4 w-4" /> Exit focus
                    </>
                  ) : (
                    <>
                      <Maximize2 className="h-4 w-4" /> Focus on course
                    </>
                  )}
                </Button>
              </div>
            </div>

            <div
              className={cn(
                "grid items-start gap-6",
                !focus && "lg:grid-cols-[minmax(0,1fr)_400px] xl:grid-cols-[minmax(0,1fr)_460px]",
              )}
            >
              {/* Pinned to the viewport on desktop, so the course stays visible while scoring.

                  The height is what makes it fit on arrival, and it is not the sticky offset:
                  the card does not start where it sticks. It starts below the page header
                  (4rem), this main's padding (1.5rem) and the row above it, which is as tall
                  as the focus button and its margin (3.25rem) — so a height measured from
                  `top-20` left its bottom edge, and with it the end of whatever lesson is
                  open, under the fold until somebody scrolled. Measured from where it starts,
                  it arrives whole; the price is that once it does stick, that difference is
                  empty space below it. Anything added back to that row has to be added here
                  too. */}
              <ConsumeContent
                url={assignment.consumable_url}
                title={assignedCourseLabel(assignment.content_title, assignment.content_id)}
                assignmentId={assignmentId}
                className="h-[70vh] lg:sticky lg:top-20 lg:h-[calc(100vh-9rem)]"
              />

              {!focus ? (
                <div className="space-y-4">
                  {/* Open, and here rather than only on the list: what the scale's bottom means
                      against what the abstention means (ADR-0052 §4) is needed while scoring,
                      not only before starting — and folded, on the one screen where it is
                      needed, it was not being read at all.

                      The form below stays open with it. Rule 1 is "read the statements first",
                      so folding them would put a click between an evaluator and the
                      instruction they have just read; opening this pushes the form down, which
                      is the order we wanted anyway.

                      Not "how this works": what works is ambiguous between our screen and the
                      course inside it, and the answer has to be our screen. */}
                  <CollapsibleSection title="How to review this course">
                    <HowThisWorks />
                  </CollapsibleSection>
                  {/* Above the form, because it is read once as context before answering —
                      the items that rest on it carry a pointer back up (ADR-0057). */}
                  <DeclaredData declared={assignment.declared} />
                  <CollapsibleSection
                    title="Your review of this course"
                    badge={`${assignment.items.length} ${unitWord(assignment)}`}
                  >
                    {/* What one submission covers, said once and next to the thing it
                        constrains. It carries the "when" too, which the heading above used to
                        carry alone: the form sits beside a single lesson, and both halves of
                        the misreading it invites — one form per lesson, answered as you go —
                        are answered here. */}
                    <p className="mb-4 text-xs text-muted-foreground">
                      Every {unitWord(assignment, 1)} is about the whole course, not the lesson
                      you have open. Answer them once, at the end.
                    </p>
                    {/* Nothing is said here about the items this course was not asked.
                        ADR-0052 §7 closes with a line for the rater — a neutral one, naming
                        no generator and no version — so that a different count between two
                        courses does not read as a bug. It is dropped on the ground that it
                        explains a discrepancy nobody can see yet: on the course in front of
                        them there is no other count to compare against, and the panel's real
                        problem is a first screen carrying more than it can hold. What is left
                        for it to say, if the first campaign asks, is `withheld_count`, which
                        the response still carries. */}
                    <ScoreForm
                      items={[...assignment.items].sort((a, b) => a.order - b.order)}
                      scaleMin={assignment.scale_min}
                      scaleMax={assignment.scale_max}
                      responseFormat={assignment.response_format}
                      submitting={submitEvaluation.isPending}
                      onSubmit={handleSubmit}
                    />
                  </CollapsibleSection>
                </div>
              ) : null}
            </div>
          </>
        )}
      </main>
    </>
  );
}
