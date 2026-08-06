"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import { useInstruments, usePublishInstrument } from "@/lib/api/hooks";
import type { InstrumentResponse } from "@/lib/api/types";

export default function InstrumentsPage() {
  const { data: instruments, isLoading, error } = useInstruments();

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Instruments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Evidential arguments: claims, verifiable criteria and designed-for bindings.
          Authoring is file-based (<code>app.cli import-instrument</code>); publishing is a
          human act — the Publish button on a draft performs it.
        </p>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !instruments || instruments.length === 0 ? (
        <EmptyState
          title="No instruments yet"
          hint="Import a draft with app.cli import-instrument --file <yaml>."
        />
      ) : (
        <div className="space-y-4">
          {instruments.map((instrument) => (
            <InstrumentCard key={instrument.instrument_version_id} instrument={instrument} />
          ))}
        </div>
      )}
    </div>
  );
}

const STATUS_VARIANT = {
  draft: "secondary",
  published: "default",
  deprecated: "outline",
} as const;

function InstrumentCard({ instrument }: { instrument: InstrumentResponse }) {
  const [open, setOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const publish = usePublishInstrument();
  const criteriaByClaim = (claimId: string) =>
    instrument.criteria.filter((c) => c.claim_ids.includes(claimId));

  function handlePublish() {
    publish.mutate(instrument.instrument_version_id, {
      onSuccess: () => {
        setConfirmOpen(false);
        toast.success("Instrument published.");
      },
      onError: (err) => {
        const e = err as ApiError;
        setConfirmOpen(false);
        if (e.status === 409) {
          toast.error("This version is already published.");
        } else if (e.status === 422) {
          toast.error("Cannot publish: the evidential argument is incomplete.", {
            description: e.message,
          });
        } else {
          toast.error("Could not publish.", { description: e.message });
        }
      },
    });
  }

  return (
    <Card>
      <CardHeader>
        {/* The collapse toggle and the Publish action are siblings: nesting a
            button inside the toggle button would be invalid HTML. */}
        <div className="flex w-full items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="flex min-w-0 flex-1 items-center gap-2 text-left"
          >
            {open ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <CardTitle>{instrument.name}</CardTitle>
            <span className="text-sm text-muted-foreground">
              {instrument.instrument_version_id}
            </span>
          </button>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="secondary">
              {instrument.claims.length} claims · {instrument.criteria.length} criteria
            </Badge>
            <Badge variant={STATUS_VARIANT[instrument.status]}>{instrument.status}</Badge>
            {instrument.status === "draft" ? (
              <Button size="sm" onClick={() => setConfirmOpen(true)}>
                Publish
              </Button>
            ) : null}
          </div>
        </div>
        {open ? (
          <p className="mt-2 text-sm text-muted-foreground">{instrument.purpose}</p>
        ) : null}
        <Dialog
          open={confirmOpen}
          onClose={() => setConfirmOpen(false)}
          title={`Publish ${instrument.instrument_version_id}?`}
        >
          <p className="text-sm text-muted-foreground">
            Publishing is irreversible: the published version becomes immutable and is the
            reference that automated assessors target and studies pin to. Any later
            adjustment — a claim&apos;s wording, a new criterion, a threshold — will require
            a new instrument version (and new versions of every assessor that targets it).
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            If the team still expects edits, make them first and publish afterwards: editing
            a draft is free; a published version never changes.
          </p>
          <div className="mt-4 flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
              disabled={publish.isPending}
            >
              Cancel
            </Button>
            <Button onClick={handlePublish} disabled={publish.isPending}>
              {publish.isPending ? <Spinner /> : null} Publish permanently
            </Button>
          </div>
        </Dialog>
      </CardHeader>
      {open ? (
        <CardContent className="space-y-4">
          {/* Ids stay out of the way (hover the statement to see them): the language of
              the workbench is the statements; ids are for lineage and dispute paths. */}
          {instrument.claims.map((claim) => (
            <div key={claim.claim_id} className="rounded-md border p-4">
              <p className="font-medium" title={claim.claim_id}>
                {claim.statement}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                qualities: {claim.quality_ids.join(", ")} · warrants:{" "}
                {claim.warrants.join(", ")} · sufficiency: {claim.sufficiency_rule}
              </p>
              <ul className="mt-3 space-y-2">
                {criteriaByClaim(claim.claim_id).map((criterion) => (
                  <li key={criterion.criterion_id} className="rounded bg-muted/40 p-3 text-sm">
                    <span className="font-medium" title={criterion.criterion_id}>
                      {criterion.statement ?? criterion.criterion_id}
                    </span>{" "}
                    — {criterion.pass_condition}
                    <span className="mt-1 block text-xs text-muted-foreground">
                      requires: {criterion.required_data.join(", ")} · on missing:{" "}
                      {criterion.on_missing_evidence}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            Designed for: {instrument.bindings.map((b) => b.package_format).join(", ")}
          </p>
        </CardContent>
      ) : null}
    </Card>
  );
}
