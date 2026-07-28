"use client";

import { useMemo, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import type { Criterion } from "@/lib/api/types";

interface Props {
  criteria: Criterion[];
  scaleMin: number;
  scaleMax: number;
  submitting: boolean;
  onSubmit: (scores: { criterion_id: string; score: number; comment: string | null }[]) => void;
}

export function ScoreForm({ criteria, scaleMin, scaleMax, submitting, onSubmit }: Props) {
  const schema = useMemo(() => {
    const shape: Record<string, z.ZodTypeAny> = {};
    for (const c of criteria) {
      shape[c.criterion_id] = z.object({
        score: z
          .number({ required_error: `Select a score (${scaleMin}–${scaleMax})` })
          .int()
          .min(scaleMin)
          .max(scaleMax),
        comment: z.string().max(2000).optional(),
      });
    }
    return z.object(shape);
  }, [criteria, scaleMin, scaleMax]);

  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Record<string, { score?: number; comment?: string }>>({
    resolver: zodResolver(schema),
  });

  const submit = handleSubmit((values) => {
    onSubmit(
      criteria.map((c) => ({
        criterion_id: c.criterion_id,
        score: values[c.criterion_id].score as number,
        comment: values[c.criterion_id].comment?.trim() || null,
      })),
    );
  });

  const scale = Array.from({ length: scaleMax - scaleMin + 1 }, (_, i) => scaleMin + i);

  // Progress replaces the old wizard stepper: how many criteria already have a score.
  const values = useWatch({ control });
  const scored = criteria.filter((c) => typeof values?.[c.criterion_id]?.score === "number").length;

  return (
    <form onSubmit={submit} className="space-y-8">
      {criteria.map((criterion, index) => {
        const fieldError = errors[criterion.criterion_id]?.score?.message as string | undefined;
        return (
          <fieldset key={criterion.criterion_id} className="space-y-3 border-t pt-6 first:border-t-0 first:pt-0">
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-medium text-muted-foreground">
                  {index + 1}/{criteria.length}
                </span>
                <h3 className="font-medium">{criterion.dimension}</h3>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{criterion.prompt}</p>
              <GuidanceDisclosure guidance={criterion.guidance} />
            </div>

            <Controller
              control={control}
              name={`${criterion.criterion_id}.score`}
              render={({ field }) => (
                <div>
                  <div className="flex flex-wrap gap-2">
                    {scale.map((value) => (
                      <button
                        key={value}
                        type="button"
                        aria-pressed={field.value === value}
                        onClick={() => field.onChange(value)}
                        className={cn(
                          "h-10 w-10 rounded-md border text-sm font-medium transition-colors",
                          field.value === value
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-input bg-background hover:bg-accent",
                        )}
                      >
                        {value}
                      </button>
                    ))}
                  </div>
                  <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
                    <span>
                      {scaleMin} · {criterion.anchor_low}
                    </span>
                    <span>
                      {criterion.anchor_high} · {scaleMax}
                    </span>
                  </div>
                  {fieldError ? (
                    <p className="mt-1 text-xs font-medium text-destructive">{fieldError}</p>
                  ) : null}
                </div>
              )}
            />

            <Textarea
              placeholder="Comment (optional)"
              rows={2}
              {...register(`${criterion.criterion_id}.comment`)}
            />
          </fieldset>
        );
      })}

      {/* Stays in reach while scrolling a long rubric (bleeds out of the section padding). */}
      <div className="sticky bottom-0 -mx-5 -mb-5 flex items-center justify-between gap-3 rounded-b-xl border-t bg-card/95 px-5 py-3 backdrop-blur">
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            {scored}/{criteria.length}
          </span>{" "}
          scored
        </p>
        <Button type="submit" disabled={submitting}>
          {submitting ? <Spinner /> : null}
          Submit evaluation
        </Button>
      </div>
    </form>
  );
}

function GuidanceDisclosure({ guidance }: { guidance: string }) {
  const [open, setOpen] = useState(false);
  if (!guidance) return null;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
        {open ? "Hide guidance" : "Show guidance"}
      </button>
      {open ? (
        <p className="mt-1.5 rounded-md bg-muted/60 p-3 text-sm text-muted-foreground">{guidance}</p>
      ) : null}
    </div>
  );
}
