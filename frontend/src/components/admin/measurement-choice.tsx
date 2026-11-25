"use client";

import { Badge } from "@/components/ui/badge";
import { TermHint } from "@/components/ui/term-hint";
import { assessorReach } from "@/lib/assessor-eligibility";
import type {
  AssessorPackageResponse,
  InstrumentResponse,
  MatchingResponse,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

/**
 * The two choices that make a measurement comparable, the instrument and the assessor, as
 * cards a reader can compare. Neither is ever preselected, even when only one is offered
 * (ADR-0042, ADR-0070 §2): choosing it is the act.
 */

function ChoiceCard({
  selected,
  onSelect,
  children,
}: {
  selected: boolean;
  onSelect: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "flex w-full flex-col gap-1.5 rounded-lg border p-4 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected ? "border-primary bg-primary/5" : "hover:bg-accent/40",
      )}
    >
      {children}
    </button>
  );
}

export function InstrumentChoice({
  instruments,
  value,
  onChange,
}: {
  /** Already narrowed to what can measure these courses. */
  instruments: InstrumentResponse[];
  value: string;
  onChange: (instrumentVersionId: string) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="flex items-center text-sm font-medium">
        What to check them against
        <TermHint term="instrument" />
      </legend>
      {instruments.length === 0 ? (
        <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
          No published instrument reads this course format. Publishing one is done on the
          Instruments page.
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {instruments.map((instrument) => (
            <ChoiceCard
              key={instrument.instrument_version_id}
              selected={value === instrument.instrument_version_id}
              onSelect={() => onChange(instrument.instrument_version_id)}
            >
              <span className="font-medium">{instrument.name}</span>
              <span className="text-xs text-muted-foreground">
                {instrument.claims.length} claims, checked by {instrument.criteria.length}{" "}
                criteria
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">
                {instrument.instrument_version_id}
              </span>
            </ChoiceCard>
          ))}
        </div>
      )}
    </fieldset>
  );
}

export function AssessorChoice({
  assessors,
  matching,
  format,
  value,
  onChange,
}: {
  /** Already narrowed to the assessors ratified against the chosen instrument. */
  assessors: AssessorPackageResponse[];
  /** What the courses' format can supply of the chosen instrument. */
  matching: MatchingResponse | undefined;
  format: string;
  value: string;
  onChange: (assessorId: string) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="flex items-center text-sm font-medium">
        Who decides the criteria
        <TermHint term="assessor" />
      </legend>
      {assessors.length === 0 ? (
        <p className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-muted-foreground">
          No assessor has ratified this instrument version yet. Ratifying is done on the
          Assessors page.
        </p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {assessors.map((pkg) => {
            const reach = assessorReach(pkg, matching);
            return (
              <ChoiceCard
                key={pkg.assessor_id ?? pkg.name}
                selected={value === pkg.assessor_id}
                onSelect={() => onChange(pkg.assessor_id ?? "")}
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{pkg.display_name}</span>
                  {pkg.uses_llm ? (
                    <Badge variant="warning">spends model calls</Badge>
                  ) : (
                    <Badge variant="success">no cost</Badge>
                  )}
                </span>
                <span className="text-xs text-muted-foreground">
                  {pkg.uses_llm
                    ? "Code, and a model that reads the course or judges it, always citing a passage."
                    : "Code only: the same course always gets the same verdict."}
                </span>
                <span className="text-xs">
                  {reach === null ? (
                    "Reading what this format can supply…"
                  ) : (
                    <>
                      Decides <strong>{reach.decides}</strong> of the {reach.supplied} criteria a{" "}
                      {format} course can supply
                      {reach.supplied < reach.total ? ` (${reach.total} in the instrument)` : ""}.
                      The other {reach.supplied - reach.decides} stay not assessed.
                    </>
                  )}
                </span>
              </ChoiceCard>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}
