"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { StudyStatusBadge } from "@/components/admin/study-status";
import { ApiError } from "@/lib/api/client";
import { useAssessorPackages, useDeclareStudy, useStudies } from "@/lib/api/hooks";
import type { StudyResponse } from "@/lib/api/types";

/** A list, and only a list. Every act on a study — pinning, composing, opening, evaluating,
 *  publishing — lives on that study's own page, in the order a round goes. */
export default function StudiesPage() {
  const { data: studies, isLoading, error } = useStudies();
  const [creating, setCreating] = useState(false);

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Evaluation studies</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            One round with a purpose: it pins a published instrument, composes a
            brief-paired dataset, opens (which freezes the dataset), is evaluated, and
            publishes an immutable report. Everything you do to a study happens on its own
            page — this is the list.
          </p>
        </div>
        <Button className="shrink-0" onClick={() => setCreating(true)}>
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
          hint="Create one above, or use app.cli declare-study --purpose <text>."
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
                  <TableHead>Assessor</TableHead>
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

      {/* Outside the list: a dialog that unmounts with what rendered it would take an
          in-flight act with it. */}
      <NewStudyDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function StudyRow({ study }: { study: StudyResponse }) {
  // The two pins side by side, because together they are what makes two rounds comparable:
  // same norm and same judge, or the numbers are not measuring the same thing (ADR-0042).
  const { data: packages } = useAssessorPackages();
  const assessor = (packages ?? []).find((pkg) => pkg.assessor_id === study.assessor_id);

  return (
    <TableRow>
      <TableCell className="font-medium">
        <Link href={`/admin/studies/${study.study_id}`} className="hover:underline">
          {study.purpose}
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

/** Asks for the name and nothing else, then goes where the work is. Declaring, pinning and
 *  composing are three acts and the domain lets them happen in any order, but a person
 *  doing them wants one place and a stated order — which is the study's own page. */
function NewStudyDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const declare = useDeclareStudy();
  const [purpose, setPurpose] = useState("");

  function create() {
    declare.mutate(
      { purpose: purpose.trim() },
      {
        onSuccess: (study) => {
          setPurpose("");
          onClose();
          toast.success("Study created.", {
            description: "Next: pin an instrument and compose the dataset.",
          });
          router.push(`/admin/studies/${study.study_id}`);
        },
        onError: (err) =>
          toast.error("Could not create the study.", {
            description: (err as ApiError).message,
          }),
      },
    );
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New study"
      description="A study is one round with a purpose. Name it here — pinning the instrument and composing the dataset happen on its own page, in order."
    >
      <Label htmlFor="study-purpose">Purpose</Label>
      <Input
        id="study-purpose"
        autoFocus
        className="mt-2"
        value={purpose}
        onChange={(e) => setPurpose(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && purpose.trim() && !declare.isPending) create();
        }}
        placeholder="e.g. First LearnpackV1 QA round"
      />
      <p className="mt-2 text-xs text-muted-foreground">
        This names the round for everyone who later reads its report, so say what it is for.
      </p>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose} disabled={declare.isPending}>
          Cancel
        </Button>
        <Button onClick={create} disabled={declare.isPending || !purpose.trim()}>
          {declare.isPending ? <Spinner /> : null} Create study
        </Button>
      </div>
    </Dialog>
  );
}
