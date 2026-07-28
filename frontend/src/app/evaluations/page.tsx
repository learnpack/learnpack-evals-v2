"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { AppHeader } from "@/components/app-header";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useMyAssignments } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

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
            {assignments.map((a) => (
              <Card key={a.assignment_id}>
                <CardContent className="flex items-center justify-between gap-4 py-4">
                  <div className="min-w-0">
                    <p className="truncate font-medium">Course {a.content_id.slice(0, 8)}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Rubric {a.rubric_version_id}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={a.status === "opened" ? "warning" : "secondary"}>
                      {a.status}
                    </Badge>
                    <Link
                      href={`/evaluations/${a.assignment_id}`}
                      className={cn(buttonVariants({ size: "sm" }))}
                    >
                      Evaluate <ArrowRight className="h-4 w-4" />
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
