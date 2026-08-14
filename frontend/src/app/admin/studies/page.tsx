"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { StudyStatusBadge } from "@/components/admin/study-status";
import { useAssessorPackages, useStudies } from "@/lib/api/hooks";
import type { StudyResponse } from "@/lib/api/types";

/** A list, and only a list. Everything done to a study — building it, evaluating it,
 *  signing it off — lives on a page of its own, and creating one is the same form a draft
 *  is edited in, so this page no longer carries a dialog of its own. */
export default function StudiesPage() {
  const router = useRouter();
  const { data: studies, isLoading, error } = useStudies();

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Evaluation studies</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            One named round: an instrument, a judge and a set of courses. It stays a draft
            until you start it — that is what fixes the three — and it ends when somebody
            signs its report off.
          </p>
        </div>
        <Button className="shrink-0" onClick={() => router.push("/admin/studies/new")}>
          <Plus className="h-4 w-4" /> New study
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !studies || studies.length === 0 ? (
        <EmptyState
          title="No studies yet"
          hint="Create one above, or use app.cli declare-study --name <text>."
        />
      ) : (
        <Card>
          <CardContent className="pt-6">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Study</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Instrument</TableHead>
                  <TableHead>Judge</TableHead>
                  <TableHead className="text-right">Briefs → courses</TableHead>
                  <TableHead className="text-right">Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Newest first, as the API answers it: the study someone is working on is
                    the one just declared. Not re-sorted here — two places deciding one
                    order is how they come to disagree. */}
                {studies.map((study) => (
                  <StudyRow key={study.study_id} study={study} />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StudyRow({ study }: { study: StudyResponse }) {
  // The instrument and the judge side by side, because together they are what makes two
  // rounds comparable: same norm and same judge, or the numbers are not measuring the same
  // thing (ADR-0042).
  const { data: packages } = useAssessorPackages();
  const assessor = (packages ?? []).find((pkg) => pkg.assessor_id === study.assessor_id);

  return (
    <TableRow>
      <TableCell className="font-medium">
        <Link href={`/admin/studies/${study.study_id}`} className="hover:underline">
          {study.name}
        </Link>
      </TableCell>
      <TableCell>
        <StudyStatusBadge status={study.status} />
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {study.instrument_version_id ? <code>{study.instrument_version_id}</code> : "—"}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {study.assessor_id ? <code>{assessor?.display_name ?? study.assessor_id}</code> : "—"}
      </TableCell>
      <TableCell className="text-right text-sm tabular-nums text-muted-foreground">
        {study.brief_ids.length} → {study.content_ids.length}
      </TableCell>
      <TableCell className="text-right text-sm tabular-nums text-muted-foreground">
        {study.created_at ? new Date(study.created_at).toLocaleDateString() : "—"}
      </TableCell>
    </TableRow>
  );
}
