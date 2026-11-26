"use client";

import { useState } from "react";
import { OutcomeBadge } from "@/components/admin/outcome-badge";
import { cn } from "@/lib/utils";

/**
 * The four ways an assessor decides a criterion, each shown with one real criterion of the
 * course drafts instrument as the thorough assessor (`drafts-hybrid` v13) decides it, per
 * `docs/MEASUREMENT.md`. The first one carries a simulator of its measure.
 *
 * The criteria and how they are decided are copied here as examples, as the README does,
 * rather than read live: this explains the mechanisms, and a test already pins the table in
 * MEASUREMENT.md to the code.
 */
type Mechanism = "code" | "extracts" | "judges" | "abstains";

const MECHANISMS: Record<
  Mechanism,
  {
    label: string;
    criterionId: string;
    statement: string;
    steps: { who: "model" | "code" | "nobody"; title: string; body: string }[];
  }
> = {
  code: {
    label: "Code decides",
    criterionId: "cr-no-lesson-spikes-in-lexical-load",
    statement: "No lesson's vocabulary runs far above the rest of the course.",
    steps: [
      {
        who: "code",
        title: "Code measures the course",
        body: "It counts, checks presence and order, or computes a measure, here the mean syllables per word of each lesson.",
      },
      {
        who: "code",
        title: "Code applies the pass condition",
        body: "No lesson more than 0.20 above the course's own median. The same course always gets the same verdict.",
      },
    ],
  },
  extracts: {
    label: "A model reads, code decides",
    criterionId: "cr-every-objective-has-an-assessment-item",
    statement:
      "Each declared objective is measured by at least one of the assessment tasks the draft offers.",
    steps: [
      {
        who: "model",
        title: "A model reads the course and returns data",
        body: "Which task measures which objective. Every item it returns is tied to a quote, and the quote is checked word for word against the course.",
      },
      {
        who: "code",
        title: "Code applies the pass condition to that data",
        body: "Every objective has at least one task: a count. The model supplied the data; it did not decide.",
      },
    ],
  },
  judges: {
    label: "A model judges",
    criterionId: "cr-closing-lesson-integrates",
    statement: "The closing lesson ties together what the course taught.",
    steps: [
      {
        who: "model",
        title: "A model answers the pass condition, citing a passage",
        body: "Used where no mechanical check exists. It is given the pass condition and the failure modes word for word.",
      },
      {
        who: "code",
        title: "Code checks and votes",
        body: "It checks the citation against the text, asks twice, a third time only if the two answers disagree, and takes the majority.",
      },
    ],
  },
  abstains: {
    label: "Nobody decides",
    criterionId: "cr-concepts-introduced-before-use",
    statement: "Each concept is introduced before the course uses it.",
    steps: [
      {
        who: "nobody",
        title: "The assessor declares that it does not check this",
        body: "With its reason, written in the assessor: it would need a map of the concepts in every lesson, which it does not extract.",
      },
      {
        who: "nobody",
        title: "The criterion ends not assessed",
        body: "Nobody decided it, human or automated. It shows as a gap in coverage, and it is not a fail.",
      },
    ],
  },
};

const ORDER: Mechanism[] = ["code", "extracts", "judges", "abstains"];

export function DecisionMechanisms({ initial = "code" }: { initial?: Mechanism }) {
  const [current, setCurrent] = useState<Mechanism>(initial);
  const mechanism = MECHANISMS[current];

  return (
    <div className="space-y-4">
      <div role="group" aria-label="How a criterion is decided" className="flex flex-wrap gap-1.5">
        {ORDER.map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={key === current}
            onClick={() => setCurrent(key)}
            className={cn(
              "rounded-md border px-3 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              key === current
                ? "border-primary bg-primary text-primary-foreground"
                : "hover:bg-accent",
            )}
          >
            {MECHANISMS[key].label}
          </button>
        ))}
      </div>

      <div aria-live="polite" className="space-y-3">
        <p className="text-sm">
          Example: <em>{mechanism.statement}</em>{" "}
          <span className="font-mono text-[11px] text-muted-foreground">
            {mechanism.criterionId}
          </span>
        </p>
        <ol className="grid gap-2 sm:grid-cols-2">
          {mechanism.steps.map((step, index) => (
            <li
              key={step.title}
              className={cn(
                "space-y-1 rounded-md border p-3 text-sm",
                step.who === "model" && "border-sky-500/50 bg-sky-500/5",
                step.who === "code" && "border-primary/40 bg-primary/5",
                step.who === "nobody" && "border-dashed",
              )}
            >
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {index + 1} · {step.who === "nobody" ? "no one" : step.who}
              </p>
              <p className="font-medium">{step.title}</p>
              <p className="text-muted-foreground">{step.body}</p>
            </li>
          ))}
        </ol>
        {current === "code" ? <LexicalLoadSimulator /> : null}
        {current === "abstains" ? (
          <p className="flex items-center gap-2 text-sm">
            <OutcomeBadge outcome="not_assessed" /> is what the report shows for it.
          </p>
        ) : null}
      </div>
    </div>
  );
}

/** Illustrative values around the real median of `object-representation-in-python` (1.656
 *  over 11 lessons), with the README's failing lesson at +0.243. The other lessons' values
 *  are invented to make the measure visible, and the simulator says so. */
const LESSONS: [string, number][] = [
  ["01.1-what-is-an-object", 1.59],
  ["01.2-attributes", 1.61],
  ["01.3-identity", 1.63],
  ["02.1-dot-notation", 1.899],
  ["02.2-methods", 1.64],
  ["02.3-self", 1.65],
  ["03.1-init", 1.656],
  ["03.2-defaults", 1.67],
  ["03.3-repr", 1.87],
  ["04.1-equality", 1.7],
  ["04.2-closing", 1.72],
];
const MARGIN = 0.2;

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function LexicalLoadSimulator() {
  const [values, setValues] = useState(LESSONS.map(([, value]) => value));
  const center = median(values);
  const above = LESSONS.map(([name], index) => ({ name, delta: values[index] - center }))
    .filter((lesson) => lesson.delta > MARGIN)
    .sort((a, b) => b.delta - a.delta);

  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-sm">
        <strong>Try it.</strong> Each slider is one lesson&apos;s mean syllables per word. Drag the
        two highest down and watch the verdict change.
      </p>
      <div className="space-y-1">
        {LESSONS.map(([name], index) => {
          const delta = values[index] - center;
          return (
            <div
              key={name}
              className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_4rem] items-center gap-2 text-xs"
            >
              <label htmlFor={`lexical-${name}`} className="truncate font-mono" title={name}>
                {name}
              </label>
              <input
                id={`lexical-${name}`}
                type="range"
                min={1.4}
                max={2.1}
                step={0.001}
                value={values[index]}
                onChange={(event) =>
                  setValues((previous) =>
                    previous.map((value, at) => (at === index ? Number(event.target.value) : value)),
                  )
                }
                className="w-full accent-primary"
              />
              <span
                className={cn(
                  "text-right font-mono tabular-nums",
                  delta > MARGIN ? "font-medium text-destructive" : "text-muted-foreground",
                )}
              >
                {delta >= 0 ? "+" : ""}
                {delta.toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>
      <div
        aria-live="polite"
        className={cn(
          "flex flex-wrap items-center gap-2 rounded-md px-3 py-2 text-sm",
          above.length ? "bg-destructive/10" : "bg-emerald-600/10",
        )}
      >
        <OutcomeBadge outcome={above.length ? "fail" : "pass"} />
        <span>
          Median {center.toFixed(3)} ·{" "}
          {above.length
            ? `${above.length} ${above.length === 1 ? "lesson" : "lessons"} more than ${MARGIN.toFixed(2)} above it; the verdict cites ${above[0].name}, at +${above[0].delta.toFixed(3)}`
            : `no lesson more than ${MARGIN.toFixed(2)} above it`}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        The median and the failing lesson are the README&apos;s real example; the other values
        are invented to show how the measure moves.
      </p>
    </div>
  );
}
