"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Check } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { MetadataList } from "@/components/metadata-list";
import { ConsumeContent } from "@/components/evaluator/consume-content";
import { ScoreForm } from "@/components/evaluator/score-form";
import { useAssignment, useOpenAssignment, useSubmitEvaluation } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const STEPS = ["Course details", "Review content", "Score"] as const;

export default function AssignmentPage({
  params,
}: {
  params: Promise<{ assignmentId: string }>;
}) {
  const { assignmentId } = use(params);
  const router = useRouter();
  const { data: assignment, isLoading, error } = useAssignment(assignmentId);
  const openAssignment = useOpenAssignment();
  const submitEvaluation = useSubmitEvaluation();
  const [step, setStep] = useState(0);

  const alreadyDone = assignment?.status === "submitted" || assignment?.status === "cancelled";

  function goToConsume() {
    // Mark opened (idempotent, best-effort — never blocks the flow).
    openAssignment.mutate(assignmentId);
    setStep(1);
  }

  function handleSubmit(scores: { criterion_id: string; score: number; comment: string | null }[]) {
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
      <main className="container max-w-3xl py-8">
        <Link
          href="/evaluations"
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to your evaluations
        </Link>

        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={(error as Error).message} />
        ) : !assignment ? (
          <ErrorState message="Assignment not found." />
        ) : alreadyDone ? (
          <Card>
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
            <Stepper step={step} />

            {step === 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle>Course details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <MetadataList metadata={assignment.metadata} />
                  <div className="flex justify-end">
                    <Button onClick={goToConsume}>Continue</Button>
                  </div>
                </CardContent>
              </Card>
            ) : step === 1 ? (
              <Card>
                <CardHeader>
                  <CardTitle>Review the content</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <ConsumeContent url={assignment.consumable_url} />
                  <div className="flex justify-between">
                    <Button variant="outline" onClick={() => setStep(0)}>
                      Back
                    </Button>
                    <Button onClick={() => setStep(2)}>Continue to scoring</Button>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Score the {assignment.criteria.length} criteria</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="mb-6">
                    <Button variant="outline" size="sm" onClick={() => setStep(1)}>
                      <ArrowLeft className="h-4 w-4" /> Back to content
                    </Button>
                  </div>
                  <ScoreForm
                    criteria={[...assignment.criteria].sort((a, b) => a.order - b.order)}
                    scaleMin={assignment.scale_min}
                    scaleMax={assignment.scale_max}
                    submitting={submitEvaluation.isPending}
                    onSubmit={handleSubmit}
                  />
                </CardContent>
              </Card>
            )}
          </>
        )}
      </main>
    </>
  );
}

function Stepper({ step }: { step: number }) {
  return (
    <ol className="mb-6 flex items-center gap-2 text-sm">
      {STEPS.map((label, i) => (
        <li key={label} className="flex items-center gap-2">
          <span
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold",
              i < step
                ? "bg-primary text-primary-foreground"
                : i === step
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground",
            )}
          >
            {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
          </span>
          <span className={cn(i === step ? "font-medium" : "text-muted-foreground")}>{label}</span>
          {i < STEPS.length - 1 ? <span className="mx-1 text-muted-foreground">→</span> : null}
        </li>
      ))}
    </ol>
  );
}
