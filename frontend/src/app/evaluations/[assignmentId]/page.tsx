"use client";

import { use, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, ExternalLink, Maximize2, Minimize2 } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { ConsumeContent } from "@/components/evaluator/consume-content";
import { ScoreForm } from "@/components/evaluator/score-form";
import { useAssignment, useOpenAssignment, useSubmitEvaluation } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

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
    scores: { criterion_id: string; score: number | null; comment: string | null }[],
  ) {
    submitEvaluation.mutate(
      { assignment_id: assignmentId, scores },
      {
        onSuccess: () => {
          toast.success("Evaluation submitted. Thank you!");
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
              <p className="font-medium">This assignment is {assignment.status}.</p>
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
              <Link
                href="/evaluations"
                className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="h-4 w-4" /> Back to your evaluations
              </Link>
              <div className="flex items-center gap-2">
                {/* No URL, no button: an anchor with no href would navigate to this page. */}
                {assignment.consumable_url ? (
                  <a href={assignment.consumable_url} target="_blank" rel="noopener noreferrer">
                    <Button variant="outline" size="sm" type="button">
                      Open in new tab <ExternalLink className="h-4 w-4" />
                    </Button>
                  </a>
                ) : null}
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
              {/* Pinned to the viewport on desktop, so the course stays visible while scoring. */}
              <ConsumeContent
                url={assignment.consumable_url}
                className="h-[70vh] lg:sticky lg:top-20 lg:h-[calc(100vh-6.5rem)]"
              />

              {!focus ? (
                <div className="space-y-4">
                  <CollapsibleSection
                    title="Score"
                    badge={`${assignment.criteria.length} items`}
                  >
                    <ScoreForm
                      criteria={[...assignment.criteria].sort((a, b) => a.order - b.order)}
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
