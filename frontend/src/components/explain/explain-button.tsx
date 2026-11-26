"use client";

import { useState } from "react";
import Link from "next/link";
import { HelpCircle } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { DecisionMechanisms } from "@/components/explain/decision-mechanisms";
import { EvidenceLadder } from "@/components/explain/evidence-ladder";
import { NoOverallScore } from "@/components/explain/no-overall-score";
import { OutcomesCalculator } from "@/components/explain/outcomes-calculator";

/** The explanations a screen can open where the question comes up. Each is also a section
 *  of `/admin/how-it-works`, which is the place to read them in order. */
const TOPICS = {
  ladder: {
    title: "From a course to the evidence",
    render: () => <EvidenceLadder />,
  },
  mechanisms: {
    title: "How a criterion is decided",
    render: () => <DecisionMechanisms />,
  },
  outcomes: {
    title: "Six outcomes, and where they count",
    render: () => <OutcomesCalculator />,
  },
  total: {
    title: "Why there is no overall score",
    render: () => <NoOverallScore />,
  },
} as const;

export type ExplainTopic = keyof typeof TOPICS;

/**
 * A small link that opens one explanation in a dialog, beside the number or the word it
 * explains. The reader stays on the page they were reading.
 */
export function ExplainButton({ topic, children }: { topic: ExplainTopic; children?: string }) {
  const [open, setOpen] = useState(false);
  const { title, render } = TOPICS[topic];
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
      >
        <HelpCircle className="h-3.5 w-3.5" aria-hidden="true" />
        {children ?? title}
      </button>
      <Dialog open={open} onClose={() => setOpen(false)} title={title} className="max-w-2xl">
        {render()}
        <p className="mt-4 text-xs text-muted-foreground">
          <Link href="/admin/how-it-works" className="text-primary hover:underline">
            How evaluation works
          </Link>{" "}
          has this and the rest, in order.
        </p>
      </Dialog>
    </>
  );
}
