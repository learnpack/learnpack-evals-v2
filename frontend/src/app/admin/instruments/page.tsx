"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useInstruments } from "@/lib/api/hooks";
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
          human act.
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
  const criteriaByClaim = (claimId: string) =>
    instrument.criteria.filter((c) => c.claim_ids.includes(claimId));

  return (
    <Card>
      <CardHeader>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex w-full items-center justify-between gap-3 text-left"
        >
          <div className="flex items-center gap-2">
            {open ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <CardTitle>{instrument.name}</CardTitle>
            <span className="text-sm text-muted-foreground">
              {instrument.instrument_version_id}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              {instrument.claims.length} claims · {instrument.criteria.length} criteria
            </Badge>
            <Badge variant={STATUS_VARIANT[instrument.status]}>{instrument.status}</Badge>
          </div>
        </button>
        {open ? (
          <p className="mt-2 text-sm text-muted-foreground">{instrument.purpose}</p>
        ) : null}
      </CardHeader>
      {open ? (
        <CardContent className="space-y-4">
          {instrument.claims.map((claim) => (
            <div key={claim.claim_id} className="rounded-md border p-4">
              <p className="font-medium">{claim.statement}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {claim.claim_id} · qualities: {claim.quality_ids.join(", ")} · warrants:{" "}
                {claim.warrants.join(", ")} · sufficiency: {claim.sufficiency_rule}
              </p>
              <ul className="mt-3 space-y-2">
                {criteriaByClaim(claim.claim_id).map((criterion) => (
                  <li key={criterion.criterion_id} className="rounded bg-muted/40 p-3 text-sm">
                    <span className="font-medium">{criterion.criterion_id}</span> —{" "}
                    {criterion.pass_condition}
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
