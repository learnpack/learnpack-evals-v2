"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import {
  useBriefs,
  useComposeStudyDataset,
  useDeclareStudy,
  useInstruments,
  useOpenStudy,
  usePinStudyInstrument,
  usePublishStudy,
  useStudies,
} from "@/lib/api/hooks";
import type { StudyResponse, StudyStatus, Uuid } from "@/lib/api/types";

const STATUS_VARIANT: Record<StudyStatus, "secondary" | "default" | "outline"> = {
  declared: "outline",
  prepared: "secondary",
  open: "default",
  published: "default",
};

export default function StudiesPage() {
  const { data: studies, isLoading, error } = useStudies();
  const declare = useDeclareStudy();
  const [purpose, setPurpose] = useState("");

  function handleDeclare() {
    declare.mutate(
      { purpose },
      {
        onSuccess: () => {
          setPurpose("");
          toast.success("Study declared.");
        },
        onError: (err) => toast.error("Could not declare.", { description: (err as ApiError).message }),
      },
    );
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Evaluation studies</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The round with a purpose: pin a published instrument, compose a brief-paired
          dataset, open it (the dataset freezes), and publish the immutable report.
          Readiness informs, it never blocks.
        </p>
      </div>

      <div className="mb-6 flex gap-2">
        <Input
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          placeholder="Purpose of the new study (e.g. First LearnpackV1 QA round)"
        />
        <Button onClick={handleDeclare} disabled={declare.isPending || !purpose.trim()}>
          {declare.isPending ? <Spinner /> : null} Declare
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !studies || studies.length === 0 ? (
        <EmptyState
          title="No studies yet"
          hint="Declare one above, or use app.cli declare-study --purpose <text>."
        />
      ) : (
        <div className="space-y-4">
          {studies.map((study) => (
            <StudyCard key={study.study_id} study={study} />
          ))}
        </div>
      )}
    </div>
  );
}

function actError(err: unknown) {
  const e = err as ApiError;
  if (e.status === 409) {
    toast.error("The study's state refuses this act.", { description: e.message });
  } else if (e.status === 422) {
    toast.error("The act is not possible yet.", { description: e.message });
  } else {
    toast.error("The act failed.", { description: e.message });
  }
}

function StudyCard({ study }: { study: StudyResponse }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex w-full items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <Link href={`/admin/studies/${study.study_id}`} className="hover:underline">
              <CardTitle>{study.purpose}</CardTitle>
            </Link>
            <p className="mt-1 text-xs text-muted-foreground">
              {study.instrument_version_id ?? "no instrument pinned"} ·{" "}
              {study.brief_ids.length} briefs → {study.content_ids.length} contents
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant={STATUS_VARIANT[study.status]}>{study.status}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <StudyActions study={study} />
      </CardContent>
    </Card>
  );
}

function StudyActions({ study }: { study: StudyResponse }) {
  const composable = study.status === "declared" || study.status === "prepared";
  return (
    <div className="flex flex-wrap items-center gap-2">
      {composable && !study.instrument_version_id ? <PinAction study={study} /> : null}
      {composable ? <ComposeAction study={study} /> : null}
      {study.status === "prepared" ? <OpenAction study={study} /> : null}
      {study.status === "open" ? <PublishAction study={study} /> : null}
      <Link
        href={`/admin/studies/${study.study_id}`}
        className="text-sm text-muted-foreground hover:underline"
      >
        {study.status === "published" ? "View report →" : "Readiness & detail →"}
      </Link>
    </div>
  );
}

function PinAction({ study }: { study: StudyResponse }) {
  const { data: instruments } = useInstruments();
  const pin = usePinStudyInstrument();
  const [selected, setSelected] = useState("");
  const published = (instruments ?? []).filter((i) => i.status === "published");

  return (
    <div className="flex items-center gap-2">
      <Select value={selected} onChange={(e) => setSelected(e.target.value)} className="w-64">
        <option value="">Pin a published instrument…</option>
        {published.map((i) => (
          <option key={i.instrument_version_id} value={i.instrument_version_id}>
            {i.instrument_version_id}
          </option>
        ))}
      </Select>
      <Button
        size="sm"
        variant="outline"
        disabled={!selected || pin.isPending}
        onClick={() =>
          pin.mutate(
            { studyId: study.study_id, body: { instrument_version_id: selected } },
            {
              onSuccess: () => toast.success("Instrument pinned — once and forever."),
              onError: actError,
            },
          )
        }
      >
        {pin.isPending ? <Spinner /> : null} Pin
      </Button>
    </div>
  );
}

function ComposeAction({ study }: { study: StudyResponse }) {
  const [open, setOpen] = useState(false);
  const { data: briefs } = useBriefs();
  const compose = useComposeStudyDataset();
  const [selected, setSelected] = useState<Uuid[]>(study.brief_ids);

  function toggle(id: Uuid) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((b) => b !== id) : [...prev, id]));
  }

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        Compose dataset
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Compose the dataset"
        description="Briefs select the registered contents generated from them. The dataset stays replaceable until the study opens."
      >
        {!briefs || briefs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No briefs registered yet. Briefs arrive mechanically when contents with a
            syllabus are registered (ADR-0022), or manually in /admin/briefs.
          </p>
        ) : (
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {briefs.map((brief) => (
              <li key={brief.brief_id}>
                <label className="flex cursor-pointer items-start gap-2 rounded border p-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.includes(brief.brief_id)}
                    onChange={() => toggle(brief.brief_id)}
                    className="mt-1"
                  />
                  <span className="line-clamp-2">{brief.brief}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={compose.isPending}
            onClick={() =>
              compose.mutate(
                { studyId: study.study_id, body: { brief_ids: selected } },
                {
                  onSuccess: (updated) => {
                    setOpen(false);
                    toast.success(
                      `Dataset composed: ${updated.content_ids.length} contents from ${updated.brief_ids.length} briefs.`,
                    );
                  },
                  onError: actError,
                },
              )
            }
          >
            {compose.isPending ? <Spinner /> : null} Compose
          </Button>
        </div>
      </Dialog>
    </>
  );
}

function OpenAction({ study }: { study: StudyResponse }) {
  const openStudy = useOpenStudy();
  return (
    <Button
      size="sm"
      disabled={openStudy.isPending}
      onClick={() =>
        openStudy.mutate(
          { studyId: study.study_id },
          {
            onSuccess: () => toast.success("Study open — the dataset is now fixed."),
            onError: actError,
          },
        )
      }
    >
      {openStudy.isPending ? <Spinner /> : null} Open
    </Button>
  );
}

function PublishAction({ study }: { study: StudyResponse }) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const publish = usePublishStudy();

  return (
    <>
      <Button size="sm" onClick={() => setConfirmOpen(true)}>
        Publish
      </Button>
      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title={`Publish "${study.purpose}"?`}
      >
        <p className="text-sm text-muted-foreground">
          Publishing is a human act and it is irreversible: the report is composed from the
          current judgments, records exactly which ones it used, and never changes again.
          Caveats — insufficient evidence, unknown generators, unaccepted adapters — are
          published with it, visibly: publishing with caveats is legitimate; publishing
          silently is impossible.
        </p>
        <div className="mt-4 flex justify-end gap-2 pt-2">
          <Button
            variant="outline"
            onClick={() => setConfirmOpen(false)}
            disabled={publish.isPending}
          >
            Cancel
          </Button>
          <Button
            disabled={publish.isPending}
            onClick={() =>
              publish.mutate(
                { studyId: study.study_id },
                {
                  onSuccess: () => {
                    setConfirmOpen(false);
                    toast.success("Study published — the report is immutable.");
                  },
                  onError: (err) => {
                    setConfirmOpen(false);
                    actError(err);
                  },
                },
              )
            }
          >
            {publish.isPending ? <Spinner /> : null} Publish permanently
          </Button>
        </div>
      </Dialog>
    </>
  );
}
