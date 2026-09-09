"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { HowThisWorks } from "@/components/evaluator/how-this-works";
import { useMyAssignments } from "@/lib/api/hooks";
import { assignedCourseLabel, courseRef } from "@/lib/courses";
import { cn } from "@/lib/utils";

/**
 * The evaluator's own words for where an assignment stands.
 *
 * `assigned` and `opened` are how the model records what happened to an assignment; neither
 * is a thing an evaluator did, and "opened" in particular reads as a fact about a file. What
 * they need from this column is whether there is work left in it. Anything else falls through
 * to the stored word rather than being renamed on a guess.
 */
const STATUS_LABELS: Record<string, string> = {
  assigned: "Not started",
  opened: "In progress",
};

export default function EvaluationsPage() {
  const { data: assignments, isLoading, error } = useMyAssignments();

  return (
    <>
      <AppHeader subtitle="Evaluator" />
      <main className="container max-w-3xl py-10">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">Your evaluations</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Courses assigned to you that are waiting for a pedagogical review.
          </p>
        </div>

        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={(error as Error).message} />
        ) : !assignments || assignments.length === 0 ? (
          <EmptyState
            title="Nothing pending"
            hint="When an admin assigns you a course it will show up here."
          />
        ) : (
          <div className="space-y-3">
            {/* Only where there is something to do with it. On an empty list it would be
                instructions for a task nobody has been given. */}
            <div className="mb-6 space-y-2 rounded-md border border-dashed bg-muted/40 p-4">
              <p className="text-xs font-medium text-foreground">Before you start</p>
              <HowThisWorks />
              {/* Outside the list, and deliberately. Those five are instructions that protect
                  the measurement and their order is not decorative; this is not a sixth one,
                  it is what happens to what they write. This is the only place the panel is
                  told — the invitation email carries no notice — so it stands where somebody
                  about to answer reads it first, and says the part that is about them. */}
              <p className="border-t pt-2 text-xs text-muted-foreground">
                Your answers are recorded under an identifier, not your name.
              </p>
            </div>
            {assignments.map((a) => (
              <Card key={a.assignment_id}>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div className="min-w-0">
                    <p className="truncate font-medium">
                      {assignedCourseLabel(a.content_title, a.content_id)}
                    </p>
                    {/* The reference stays even when the course has a name: two courses of
                        one commission declare the same title, and this is what an evaluator
                        quotes when one of them will not load. What is NOT here is the
                        external id or the instrument version — see ADR-0059 §5.

                        Read short and copied whole: the eight characters are what somebody
                        reads out loud, the full id is what an admin needs pasted back. */}
                    <CopyButton
                      value={a.content_id}
                      label={`Course ID ${courseRef(a.content_id)}`}
                      className="mt-1 border-transparent px-0 hover:bg-transparent"
                    />
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={a.status === "opened" ? "warning" : "secondary"}>
                      {STATUS_LABELS[a.status] ?? a.status}
                    </Badge>
                    <Link
                      href={`/evaluations/${a.assignment_id}`}
                      className={cn(buttonVariants({ size: "sm" }))}
                    >
                      {/* The only "I already started this" the list can offer. */}
                      {a.status === "opened" ? "Continue review" : "Start review"}{" "}
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
