"use client";

import { useState } from "react";

/**
 * Why a course is never reduced to one number (ADR-0011), shown rather than argued: two
 * generator versions, five dimensions, and weights the reader moves. Any total needs weights,
 * and the weights decide which version comes out ahead.
 *
 * The values are invented and labelled so. They are chosen so that equal weights favour one
 * version and weighting alignment and progression favours the other.
 */
const DIMENSIONS: { name: string; a: number; b: number }[] = [
  { name: "Objectives", a: 0.85, b: 0.55 },
  { name: "Constructive alignment", a: 0.4, b: 0.7 },
  { name: "Instructional design", a: 0.8, b: 0.6 },
  { name: "Coherence between lessons", a: 0.7, b: 0.65 },
  { name: "Learning progression", a: 0.55, b: 0.75 },
];

export function NoOverallScore() {
  const [weights, setWeights] = useState(DIMENSIONS.map(() => 1));
  const sum = weights.reduce((total, weight) => total + weight, 0);
  const mean = (key: "a" | "b") =>
    sum === 0
      ? null
      : DIMENSIONS.reduce((total, dimension, index) => total + dimension[key] * weights[index], 0) /
        sum;
  const a = mean("a");
  const b = mean("b");
  const verdict =
    a === null || b === null
      ? "No weights, no total."
      : Math.abs(a - b) < 0.0005
        ? "A tie."
        : `Version ${a > b ? "A" : "B"} comes out ahead with these weights.`;

  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div className="space-y-1">
        <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Weight of each dimension
        </p>
        {DIMENSIONS.map((dimension, index) => (
          <div
            key={dimension.name}
            className="grid grid-cols-[minmax(0,1fr)_6rem_1.5rem] items-center gap-2 text-sm"
          >
            <label htmlFor={`weight-${index}`} className="min-w-0">
              {dimension.name}
              <span className="ml-1 font-mono text-[11px] text-muted-foreground">
                A {dimension.a.toFixed(2)} · B {dimension.b.toFixed(2)}
              </span>
            </label>
            <input
              id={`weight-${index}`}
              type="range"
              min={0}
              max={3}
              step={1}
              value={weights[index]}
              onChange={(event) =>
                setWeights((previous) =>
                  previous.map((weight, at) => (at === index ? Number(event.target.value) : weight)),
                )
              }
              className="w-full accent-primary"
            />
            <output htmlFor={`weight-${index}`} className="text-right font-mono tabular-nums">
              {weights[index]}
            </output>
          </div>
        ))}
      </div>
      <div className="space-y-3" aria-live="polite">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="py-1.5 font-medium">Version</th>
              <th className="py-1.5 text-right font-medium">Weighted mean</th>
            </tr>
          </thead>
          <tbody>
            {(
              [
                ["Version A", a],
                ["Version B", b],
              ] as const
            ).map(([label, value]) => (
              <tr key={label} className="border-b last:border-0">
                <td className="py-1.5">{label}</td>
                <td className="py-1.5 text-right font-mono tabular-nums">
                  {value === null ? "—" : value.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="font-medium">{verdict}</p>
        <p className="text-sm text-muted-foreground">
          Choosing the weights is a judgment about what matters, and the instrument does not make
          it for you. The console shows each dimension and each claim. If your work needs one
          number, choose the weights yourself and write them down. The values here are
          invented.
        </p>
      </div>
    </div>
  );
}
