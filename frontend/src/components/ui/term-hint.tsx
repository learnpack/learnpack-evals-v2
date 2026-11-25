import { HelpCircle } from "lucide-react";
import { Popover } from "@/components/ui/popover";
import { TERMS, type Term } from "@/lib/terms";

/**
 * The "?" beside a term the reader may not know (ADR-0069 §2). It opens one sentence and
 * nothing else: a definition the reader has to leave the screen for is one they skip.
 */
export function TermHint({ term }: { term: Term }) {
  return (
    <Popover
      label={`What is a ${term}?`}
      trigger={<HelpCircle className="ml-1 h-3.5 w-3.5" aria-hidden="true" />}
    >
      <span className="mb-1 block font-medium capitalize">{term}</span>
      {TERMS[term]}
    </Popover>
  );
}
