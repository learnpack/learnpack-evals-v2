"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

/** Copying an identifier out of a report is a COPY task, not a read task.
 *
 *  That distinction is the whole reason ids stopped being row labels: they are needed, but
 *  they are needed in an editor, not in a sentence. A monospace chip that hands itself over
 *  on one click serves that better than prominence ever did.
 *
 *  `navigator.clipboard` needs a secure context — fine on localhost and on Netlify. Where it
 *  is not, the promise rejects and the button would silently do nothing, so the failure is
 *  reported rather than swallowed. */
export function CopyButton({
  value,
  label,
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      title={`Copy ${value}`}
      onClick={() => {
        navigator.clipboard
          .writeText(value)
          .then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1200);
          })
          .catch(() =>
            toast.error("Could not copy.", {
              description: "The clipboard needs a secure context (https or localhost).",
            }),
          );
      }}
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
        className,
      )}
    >
      <span className="truncate">{label ?? value}</span>
      {copied ? (
        <Check className="h-3 w-3 shrink-0 text-emerald-600" />
      ) : (
        <Copy className="h-3 w-3 shrink-0" />
      )}
    </button>
  );
}
