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
                {/* The screen says which course it is asking about (ADR-0059 §5): the name
                    the course declares, and the reference to quote if it will not load. */}
                <h1 className="mt-1 truncate text-lg font-semibold tracking-tight">
                  {assignedCourseLabel(assignment.content_title, assignment.content_id)}
                </h1>
                {/* What is being asked for, said where the eye already is. The form sits beside
                    one lesson, so the screen has to contradict the reading that proximity
                    invites — the first expert to see it asked whether it was one form per
                    lesson. The count comes from the items served and never from a literal:
                    a course that declares less is asked fewer of them (ADR-0053). */}
                <p className="mt-0.5 text-xs text-muted-foreground">
                  One review per course · {assignment.items.length} {unitWord(assignment)},
                  answered once at the end
                </p>
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
                  (4rem), this main's padding (1.5rem) and the heading block that names the
                  course (~4.4rem) — so a height measured from `top-20` left its bottom edge,
                  and with it the end of whatever lesson is open, under the fold until somebody
                  scrolled. Measured from where it starts, it arrives whole; the price is that
                  once it does stick, that difference is empty space below it. */}
              <ConsumeContent
                url={assignment.consumable_url}
                title={assignedCourseLabel(assignment.content_title, assignment.content_id)}
                assignmentId={assignmentId}
                className="h-[70vh] lg:sticky lg:top-20 lg:h-[calc(100vh-11rem)]"
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
                    {/* The same thing the heading says, said again where the answering happens:
                        by the time somebody has scrolled to the form, the heading is gone. */}
                    <p className="mb-4 text-xs text-muted-foreground">
                      Every {unitWord(assignment, 1)} is about the whole course, not the lesson
                      you have open.
                    </p>
                    {assignment.withheld_count > 0 ? (
                      /* Said, rather than left as a silent gap: an evaluator who scores two
                         courses notices a different number of items and reads it as a bug.
                         It names no generator and no version — the panel stays blind to
                         which one made a course (ADR-0053). */
                      <p className="mb-5 rounded-md border border-dashed bg-muted/40 p-3 text-xs text-muted-foreground">
                        Some items are not shown for this course, because it does not declare
                        what they ask about. Answer the ones below.
                      </p>
                    ) : null}
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
