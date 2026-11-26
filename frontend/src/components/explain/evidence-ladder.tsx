"use client";

import { useState, type ReactNode } from "react";
import { ClaimStatusBadge } from "@/components/admin/claim-status";
import { OutcomeBadge } from "@/components/admin/outcome-badge";
import { cn } from "@/lib/utils";

/**
 * From a dimension down to the passage a verdict rests on, one step at a time.
 *
 * The example is the one the root README walks through, and it is copied here as an example
 * on purpose rather than read from the live instrument: this explains how results are built,
 * and an explanation that changed whenever an instrument was bumped would teach a moving
 * target. Everything in it is labelled as an example.
 */
const RUNGS: { level: string; name: string; body: ReactNode }[] = [
  {
    level: "Dimension",
    name: "Learning progression",
    body: (
      <p>
        One of five broad areas a course is looked at from. A dimension groups several
        qualities. Results are read dimension by dimension, and never added up into one
        number for the course.
      </p>
    ),
  },
  {
    level: "Quality",
    name: "Increasing and level-appropriate cognitive demand",
    body: (
      <p>
        One pedagogical property a course can have: <em>cognitive demand grows across the
        course and stays appropriate for the audience.</em> Experts rate qualities from 1 to 5.
        The automated side reaches a quality through the claims about it.
      </p>
    ),
  },
  {
    level: "Claim",
    name: "No single lesson's text runs far ahead of the course's own level.",
    body: (
      <div className="space-y-2">
        <p>
          A one-sentence assertion about one quality, which the instrument sets out to verify.
          For each course it ends in one of three states:
        </p>
        <ul className="space-y-1.5">
          <li>
            <ClaimStatusBadge status="supported" /> every criterion under it passed.
          </li>
          <li>
            <ClaimStatusBadge status="refuted" /> at least one criterion failed. One cited
            counterexample is enough.
          </li>
          <li>
            <ClaimStatusBadge status="insufficient" /> nothing failed, but not everything
            passed either: a criterion had no evidence, was not assessed, did not apply to
            this format, or the run failed on it. This is the absence of a verdict, not a mild
            one.
          </li>
        </ul>
        <p>
          Over a study, a claim is read as how many courses supported it, refuted it or left
          it insufficient, out of the courses that were evaluated.
        </p>
      </div>
    ),
  },
  {
    level: "Criterion",
    name: "No lesson's vocabulary runs far above the rest of the course.",
    body: (
      <div className="space-y-2">
        <p>One condition that can be checked, with a written pass condition:</p>
        <blockquote className="rounded border bg-muted/40 px-3 py-2 font-mono text-xs">
          No lesson&apos;s mean syllables per word exceeds the course&apos;s own median by more
          than 0.20.
        </blockquote>
        <p>
          The instrument says what is checked. The assessor decides how: for this criterion,
          code computes the measure and applies the threshold, and no model is involved.
        </p>
      </div>
    ),
  },
  {
    level: "Evidence",
    name: "Lesson 02.1-dot-notation",
    body: (
      <div className="space-y-2">
        <p>
          In the course <code>object-representation-in-python</code>, the assessor measures 11
          lessons. The median is 1.656, and this lesson sits <strong>0.243</strong> above it,
          past the 0.20 margin. The criterion ends:
        </p>
        <p className="flex flex-wrap items-center gap-2">
          <OutcomeBadge outcome="fail" />
          <span className="text-muted-foreground">
            “One lesson is written for a markedly more advanced reader than the rest of the
            course.”
          </span>
        </p>
        <p>
          The verdict carries the lesson text it measured and where that text sits in the
          package. A verdict always cites its evidence, or records that there was none.
        </p>
      </div>
    ),
  },
];

export function EvidenceLadder({ initial = 3 }: { initial?: number }) {
  const [current, setCurrent] = useState(initial);
  const rung = RUNGS[current];

  return (
    <div className="space-y-4">
      {/* Toggle buttons rather than a tablist: five steps of one example, read in any order,
          and a group of pressed buttons needs no arrow-key contract to be accessible. */}
      <div role="group" aria-label="From a dimension to its evidence" className="grid gap-1.5 sm:grid-cols-5">
        {RUNGS.map((step, index) => (
          <button
            key={step.level}
            type="button"
            aria-pressed={index === current}
            onClick={() => setCurrent(index)}
            className={cn(
              "flex min-w-0 flex-col rounded-md border px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              index === current
                ? "border-primary bg-primary text-primary-foreground"
                : "hover:bg-accent",
            )}
          >
            <span
              className={cn(
                "text-[11px] uppercase tracking-wider",
                index === current ? "text-primary-foreground/80" : "text-muted-foreground",
              )}
            >
              {index + 1} · {step.level}
            </span>
            <span className="line-clamp-2 text-sm font-medium">{step.name}</span>
          </button>
        ))}
      </div>
      <div aria-live="polite" className="space-y-2 border-l-2 border-primary pl-4 text-sm">
        <p className="font-medium">
          {rung.level}: {rung.name}
        </p>
        {rung.body}
      </div>
      <p className="text-xs text-muted-foreground">
        Example from the course drafts instrument and one of the courses its thresholds were
        set against.
      </p>
    </div>
  );
}
