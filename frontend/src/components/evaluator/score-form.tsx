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

/**
 * Two elicitations, one form.
 *
 * - **`likert`** (ADR-0052): each item is a *statement* and the answer is agreement with it,
 *   on the same five points for every item. The rater learns the scale once and never
 *   changes frame, which is what lets twelve items cost less than five anchored ones did.
 * - **`numeric`**: the older shape — a question, numbered buttons, and a per-item anchor at
 *   each end.
 *
 * Both carry the same off-scale escape. **`ABSTAIN` is not the bottom of the scale**: the
 * bottom is an answer ("the course does not do this") and has to weigh like one, while an
 * abstention says the rater could not see enough to judge and is stored as a null score.
 * Collapsing the two would silently turn "I don't know" into the worst possible verdict.
 */

type Scores = { criterion_id: string; score: number | null; comment: string | null }[];

/**
 * `preview` is a discriminated arm rather than a flag so the compiler enforces the rule:
 * in preview there is no submit handler to call, and the admin console cannot record an
 * answer by accident. The two modes share every other prop because they must render the
 * same form — a preview that drifts from the real one lies about the only thing it shows.
 */
type Props = {
  criteria: Criterion[];
  scaleMin: number;
  scaleMax: number;
  responseFormat: string;
} & (
  | { preview: true; submitting?: never; onSubmit?: never }
  | { preview?: false; submitting: boolean; onSubmit: (scores: Scores) => void }
);

/** The sentinel for the off-scale answer. A string, so it can never collide with a point. */
const ABSTAIN = "abstain" as const;

/** Uniform across every item — that uniformity is what makes it a Likert scale. */
const AGREEMENT_LABELS = [
  "Strongly disagree",
  "Disagree",
  "Neither",
  "Agree",
  "Strongly agree",
] as const;

export function ScoreForm({
  criteria,
  scaleMin,
  scaleMax,
  responseFormat,
  preview = false,
  submitting,
  onSubmit,
}: Props) {
  const likert = responseFormat === "likert";

  const schema = useMemo(() => {
    const shape: Record<string, z.ZodTypeAny> = {};
    for (const c of criteria) {
      shape[c.criterion_id] = z.object({
        // Required, and satisfied by either an answer or an explicit abstention — never by
        // leaving the item alone. Silence is not an answer of any kind.
        answer: z.union([z.number().int().min(scaleMin).max(scaleMax), z.literal(ABSTAIN)], {
          required_error: likert ? "Answer or skip this statement" : "Score or skip this criterion",
        }),
        comment: z.string().max(2000).optional(),
      });
    }
    return z.object(shape);
  }, [criteria, scaleMin, scaleMax, likert]);

  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Record<string, { answer?: number | typeof ABSTAIN; comment?: string }>>({
    resolver: zodResolver(schema),
  });

  const submit = handleSubmit((values) => {
    if (!onSubmit) return; // preview: unreachable, the footer offers nothing to submit
    onSubmit(
      criteria.map((c) => {
        const answer = values[c.criterion_id].answer;
        return {
          criterion_id: c.criterion_id,
          score: answer === ABSTAIN ? null : (answer as number),
          comment: values[c.criterion_id].comment?.trim() || null,
        };
      }),
    );
  });

  const scale = Array.from({ length: scaleMax - scaleMin + 1 }, (_, i) => scaleMin + i);

  // Progress: how many items have been answered. An abstention counts — it is an answer
  // about the rater's evidence, not a blank.
  const values = useWatch({ control });
  const answered = criteria.filter((c) => values?.[c.criterion_id]?.answer !== undefined).length;

  return (
    <form onSubmit={submit} className="space-y-8">
      {criteria.map((criterion, index) => {
        const fieldError = errors[criterion.criterion_id]?.answer?.message as string | undefined;
        return (
          <fieldset
            key={criterion.criterion_id}
            className="space-y-3 border-t pt-6 first:border-t-0 first:pt-0"
          >
            <div>
              <div className="flex items-baseline gap-2">
                <span className="text-xs font-medium text-muted-foreground">
                  {index + 1}/{criteria.length}
                </span>
                {/* A Likert form is statements, not sections: the dimension is a grouping for
                    reports, and showing it here would only invite scoring the group. */}
                {!likert ? <h3 className="font-medium">{criterion.dimension}</h3> : null}
              </div>
              <p className={cn("mt-1 text-sm", likert ? "text-foreground" : "text-muted-foreground")}>
                {criterion.prompt}
              </p>
              {/* The cost of putting the declarations above the form: by item 3 they have
                  scrolled away. One line, no anchor — a reminder that the material is there. */}
              {criterion.required_data.length > 0 && !preview ? (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Rests on what the course declares, above.
                </p>
              ) : null}
              <GuidanceDisclosure guidance={criterion.guidance} likert={likert} />
            </div>

            <Controller
              control={control}
              name={`${criterion.criterion_id}.answer`}
              render={({ field }) => (
                <div>
                  {likert ? (
                    <div className="grid grid-cols-5 gap-1.5">
                      {scale.map((value, i) => (
                        <button
                          key={value}
                          type="button"
                          aria-pressed={field.value === value}
                          onClick={() => field.onChange(value)}
                          className={cn(
                            "rounded-md border px-1 py-2 text-[11px] font-medium leading-tight transition-colors",
                            field.value === value
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-input bg-background hover:bg-accent",
                          )}
                        >
                          {AGREEMENT_LABELS[i] ?? value}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <>
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
                    </>
                  )}

                  {/* Set apart from the row on purpose: it is not a sixth point. */}
                  <button
                    type="button"
                    aria-pressed={field.value === ABSTAIN}
                    onClick={() => field.onChange(field.value === ABSTAIN ? undefined : ABSTAIN)}
                    className={cn(
                      "mt-2 w-full rounded-md border border-dashed px-2 py-1.5 text-xs transition-colors",
                      field.value === ABSTAIN
                        ? "border-foreground/40 bg-muted font-medium text-foreground"
                        : "border-input text-muted-foreground hover:bg-accent",
                    )}
                  >
                    I couldn&apos;t see enough of this course to judge this
                  </button>

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

      {/* Stays in reach while scrolling a long instrument (bleeds out of the section padding). */}
      <div className="sticky bottom-0 -mx-5 -mb-5 flex items-center justify-between gap-3 rounded-b-xl border-t bg-card/95 px-5 py-3 backdrop-blur">
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            {answered}/{criteria.length}
          </span>{" "}
          answered
        </p>
        {/* The counter stays in preview — clicking through the scale is how somebody
            reviewing the instrument notices that a statement reads wrong. What goes is the
            act: no button, so there is nothing to press by mistake. */}
        {preview ? (
          <p className="text-xs text-muted-foreground">Nothing here is recorded</p>
        ) : (
          <Button type="submit" disabled={submitting}>
            {submitting ? <Spinner /> : null}
            Submit evaluation
          </Button>
        )}
      </div>
    </form>
  );
}

function GuidanceDisclosure({ guidance, likert }: { guidance: string; likert: boolean }) {
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
        {open ? "Hide guidance" : likert ? "What agreeing means" : "Show guidance"}
      </button>
      {open ? (
        <p className="mt-1.5 rounded-md bg-muted/60 p-3 text-sm text-muted-foreground">{guidance}</p>
      ) : null}
    </div>
  );
}
