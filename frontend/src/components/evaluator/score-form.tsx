"use client";

import { useId, useMemo, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ChevronDown, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import type { RubricItem } from "@/lib/api/types";

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

type Scores = { quality_id: string; score: number | null; comment: string | null }[];

/**
 * `preview` is a discriminated arm rather than a flag so the compiler enforces the rule:
 * in preview there is no submit handler to call, and the admin console cannot record an
 * answer by accident. The two modes share every other prop because they must render the
 * same form — a preview that drifts from the real one lies about the only thing it shows.
 */
type Props = {
  items: RubricItem[];
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

/**
 * What a folded item says the rater chose. In likert it is the words and never the number:
 * the scale *is* its labels, and a folded "4" is not something anybody can check at a glance.
 * Indexed from `scaleMin`, the way the open row indexes them — `answer - 1` would be right
 * only for a scale that happens to start at one.
 */
function answerLabel(
  answer: number | typeof ABSTAIN | undefined,
  likert: boolean,
  scaleMin: number,
) {
  if (answer === undefined) return "Not answered";
  if (answer === ABSTAIN) return "Couldn't judge";
  return likert ? (AGREEMENT_LABELS[answer - scaleMin] ?? String(answer)) : String(answer);
}

export function ScoreForm({
  items,
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
    for (const item of items) {
      shape[item.quality_id] = z.object({
        // Required, and satisfied by either an answer or an explicit abstention — never by
        // leaving the item alone. Silence is not an answer of any kind.
        answer: z.union([z.number().int().min(scaleMin).max(scaleMax), z.literal(ABSTAIN)], {
          required_error: likert ? "Answer or skip this statement" : "Score or skip this item",
        }),
        comment: z.string().max(2000).optional(),
      });
    }
    return z.object(shape);
  }, [items, scaleMin, scaleMax, likert]);

  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Record<string, { answer?: number | typeof ABSTAIN; comment?: string }>>({
    resolver: zodResolver(schema),
  });

  const submit = handleSubmit(
    (values) => {
      if (!onSubmit) return; // preview: unreachable, the footer offers nothing to submit
      onSubmit(
        items.map((item) => {
          const answer = values[item.quality_id].answer;
          return {
            quality_id: item.quality_id,
            score: answer === ABSTAIN ? null : (answer as number),
            comment: values[item.quality_id].comment?.trim() || null,
          };
        }),
      );
    },
    () => {
      // A failed submit is the one moment the form overrules the rater about what is folded:
      // they are being asked to fix something, and an error nobody can see is an error nobody
      // can fix. Dropping the standing preference hands every item back to the rule below,
      // which opens exactly the unanswered ones.
      setActive(null);
    },
  );

  const scale = Array.from({ length: scaleMax - scaleMin + 1 }, (_, i) => scaleMin + i);

  // Progress: how many items have been answered. An abstention counts — it is an answer
  // about the rater's evidence, not a blank.
  const values = useWatch({ control });
  const answered = items.filter((item) => values?.[item.quality_id]?.answer !== undefined).length;

  /**
   * Folding is *derived* from the answer, so it can never drift from the form: an item is
   * folded because it has been answered. `active` is the single exception, and it is about
   * this moment rather than a remembered preference.
   *
   * - `id` alone — the rater is standing in this item, so it stays open even once answered.
   *   This is why folding is not on the click: clicking a point focuses that button, so an
   *   item never folds out from under the click that answered it, and the comment box does
   *   not vanish at the moment the rater has just formed an opinion. It folds when they move
   *   on, which is when folding is a relief rather than a theft.
   * - `open` — they pressed the header. Explicit, because Safari does not focus a button on
   *   click, so expanding cannot be left to focus alone.
   *
   * Both die when focus leaves the item, so what a rater walks away from is always the
   * derived state and the panel keeps shrinking on its own. An unanswered item therefore
   * cannot be folded away for good — which is the point of the whole thing.
   */
  const [active, setActive] = useState<{ id: string; open?: boolean } | null>(null);
  const isOpen = (id: string) =>
    active?.id === id ? (active.open ?? true) : values?.[id]?.answer === undefined;

  // Two forms on one page (the admin preview beside anything else) would otherwise collide
  // on `quality_id` as an element id.
  const formId = useId();

  return (
    <form onSubmit={submit} className="space-y-8">
      {items.map((item, index) => {
        const fieldError = errors[item.quality_id]?.answer?.message as string | undefined;
        const commentError = errors[item.quality_id]?.comment?.message as string | undefined;
        const answer = values?.[item.quality_id]?.answer;
        const hasComment = Boolean(values?.[item.quality_id]?.comment?.trim());
        const open = isOpen(item.quality_id);
        const bodyId = `${formId}-${item.quality_id}`;
        return (
          <fieldset
            key={item.quality_id}
            className={cn(
              "space-y-3 border-t first:border-t-0 first:pt-0",
              // Twelve folded rows should not read as twelve empty bands.
              open ? "pt-6" : "pt-3",
            )}
            // React's onFocus/onBlur are focusin/focusout, so one pair here covers every
            // control in the item — the points, abstain, the guidance toggle, the comment.
            onFocus={() =>
              setActive((a) => (a?.id === item.quality_id ? a : { id: item.quality_id }))
            }
            onBlur={(e) => {
              if (e.currentTarget.contains(e.relatedTarget)) return; // moved within the item
              setActive((a) => (a?.id === item.quality_id ? null : a));
            }}
          >
            {/* The statement is the toggle, the way a CollapsibleSection's title is — and it
                is mounted in both states on purpose: a trigger that disappears when pressed
                drops keyboard focus onto <body> and returns a screen-reader user to the top
                of the page. */}
            <button
              type="button"
              aria-expanded={open}
              aria-controls={bodyId}
              onClick={() => setActive({ id: item.quality_id, open: !open })}
              className="-mx-2 flex w-full items-start gap-2 rounded-md px-2 py-1 text-left transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ChevronDown
                className={cn(
                  "mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none",
                  !open && "-rotate-90",
                )}
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    {index + 1}/{items.length}
                  </span>
                  {/* A Likert form is statements, not sections: the dimension is a grouping
                      for reports, and showing it here would only invite scoring the group. */}
                  {!likert && open ? <span className="font-medium">{item.dimension}</span> : null}
                </span>
                {/* The statement has to outrank everything around it: it is what is being
                    judged, and the guidance, the pointer and the scale labels are all there to
                    serve it. At one size for all of them the eye lands on the five buttons —
                    the loudest shape — rather than on the question. Likert only: in numeric
                    mode the dimension heading carries the weight and the prompt sits under it.
                    Folded, it steps back to a single truncated line: what the row is for then
                    is saying which item this was and what was answered. */}
                <span
                  className={cn(
                    "mt-1 block",
                    open
                      ? likert
                        ? "text-[15px] font-medium leading-snug text-foreground"
                        : "text-sm text-muted-foreground"
                      : "truncate text-sm text-muted-foreground",
                  )}
                >
                  {item.prompt}
                </span>
              </span>
              {!open ? (
                <span className="flex shrink-0 items-center gap-1.5 pt-0.5">
                  {/* Folding must not hide written work with nothing to say it is there. */}
                  {hasComment ? (
                    <>
                      <MessageSquare className="h-3 w-3 text-muted-foreground" aria-hidden />
                      <span className="sr-only">has a comment</span>
                    </>
                  ) : null}
                  <span
                    className={cn(
                      "rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-tight",
                      answer === ABSTAIN
                        ? "border-dashed border-foreground/40 bg-muted text-muted-foreground"
                        : "border-primary/40 bg-primary/10 text-foreground",
                    )}
                  >
                    {answerLabel(answer, likert, scaleMin)}
                  </span>
                </span>
              ) : null}
            </button>

            {/* Hidden, never unmounted. `shouldUnregister` is false today, so a value would
                survive — but that is a default of the library, not a property of this file,
                and someone turning it on for an unrelated reason would silently empty every
                folded item. Staying mounted also keeps what remounting would not restore: the
                caret in a half-written comment, and the guidance panel a rater left open.
                Both the attribute and the class, because `[hidden]` is a UA rule that any
                author `display:` utility beats — leaving content invisible but still read
                aloud. */}
            <div id={bodyId} hidden={!open} className={cn("space-y-3", !open && "hidden")}>
              {/* The cost of putting the declarations above the form: by item 3 they have
                  scrolled away. One line, no anchor — a reminder that the material is there. */}
              {item.required_data.length > 0 && !preview ? (
                <p className="text-xs text-muted-foreground">
                  Rests on what the course declares, above.
                </p>
              ) : null}
              <GuidanceDisclosure guidance={item.guidance} likert={likert} />

              <Controller
                control={control}
                name={`${item.quality_id}.answer`}
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
                            {scaleMin} · {item.anchor_low}
                          </span>
                          <span>
                            {item.anchor_high} · {scaleMax}
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
                // The schema's own cap, said to the browser as well: without it a long paste
                // fails the submit with a message this form had nowhere to show.
                maxLength={2000}
                {...register(`${item.quality_id}.comment`)}
              />
              {commentError ? (
                <p className="text-xs font-medium text-destructive">{commentError}</p>
              ) : null}
            </div>
          </fieldset>
        );
      })}

      {/* Stays in reach while scrolling a long instrument (bleeds out of the section padding). */}
      <div className="sticky bottom-0 -mx-5 -mb-5 flex items-center justify-between gap-3 rounded-b-xl border-t bg-card/95 px-5 py-3 backdrop-blur">
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            {answered}/{items.length}
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

const AGREE_LEAD = "Agree if";
const DISAGREE_LEAD = "Disagree if";

/**
 * The two halves of a guidance, told apart.
 *
 * ADR-0052 §3 writes each item's guidance as an **Agree** half and a **Disagree** half, *each
 * standing on its own*, so a rater reads the one they are leaning towards instead of a
 * paragraph written as the continuation of the other. One block under a label naming only the
 * Agree half did neither: it read as a single explanation, and it named the pole it was about
 * to lean the reader towards.
 *
 * The shape lives in the text — every v2 item reads `[preamble] Agree if … Disagree if …` — so
 * that is what this splits on. Anything else falls back to the whole string, unsplit: rubric
 * v1 is worded differently, is no longer seeded but still resolves for a campaign pinned to
 * it, and the admin preview renders whatever version the store holds.
 */
function splitGuidance(guidance: string) {
  // Capital A on purpose: "Disagree if" does not contain "Agree if", so the first match is
  // the Agree half and never the tail of the other one.
  const agree = guidance.indexOf(AGREE_LEAD);
  const disagree = guidance.indexOf(DISAGREE_LEAD);
  if (agree === -1 || disagree === -1 || disagree < agree) return null;
  return {
    preamble: guidance.slice(0, agree).trim(),
    agree: guidance.slice(agree + AGREE_LEAD.length, disagree).trim(),
    disagree: guidance.slice(disagree + DISAGREE_LEAD.length).trim(),
  };
}

function GuidanceDisclosure({ guidance, likert }: { guidance: string; likert: boolean }) {
  const [open, setOpen] = useState(false);
  const halves = useMemo(() => splitGuidance(guidance), [guidance]);
  if (!guidance) return null;
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
        {/* Neutral on purpose: the label names the act, not one of the two poles. */}
        {open ? "Hide guidance" : likert ? "How to decide" : "Show guidance"}
      </button>
      {open ? (
        <div className="mt-1.5 space-y-2 rounded-md bg-muted/60 p-3 text-sm text-muted-foreground">
          {halves ? (
            <>
              {halves.preamble ? <p>{halves.preamble}</p> : null}
              <p>
                <span className="font-medium text-foreground">{AGREE_LEAD}</span>{" "}
                {halves.agree}
              </p>
              <p>
                <span className="font-medium text-foreground">{DISAGREE_LEAD}</span>{" "}
                {halves.disagree}
              </p>
            </>
          ) : (
            <p>{guidance}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
