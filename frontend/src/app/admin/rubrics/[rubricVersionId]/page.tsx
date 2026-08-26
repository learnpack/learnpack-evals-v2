"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { ScoreForm } from "@/components/evaluator/score-form";
import { useReferenceInstrument } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";
import type { RubricCriterion } from "@/lib/api/types";

type View = "items" | "preview";

/**
 * One rubric, seen the two ways it needs to be seen.
 *
 * **Items** is the instrument as data — the quality each statement elicits, what grounds it,
 * what a course must declare for it to be asked at all. None of that reaches the form, and
 * before this page it lived only in the seed file.
 *
 * **Preview** is the instrument as felt, and it is the evaluator's own `ScoreForm`, not a
 * copy: a second implementation would drift, and a preview that drifts lies about the one
 * thing it exists to show.
 *
 * The view is local state rather than a `?view=` param. The route already is the shareable
 * unit, and `useSearchParams` needs a Suspense boundary that only `npm run build` catches.
 */
export default function RubricDetailPage({
  params,
}: {
  params: Promise<{ rubricVersionId: string }>;
}) {
  const { rubricVersionId } = use(params);
  const { data: rubric, isLoading, error } = useReferenceInstrument(rubricVersionId);
  const [view, setView] = useState<View>("items");

  const items = useMemo(
    () => [...(rubric?.criteria ?? [])].sort((a, b) => a.order - b.order),
    [rubric],
  );

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!rubric) return <ErrorState message="Rubric not found." />;

  return (
    <div className="max-w-4xl">
      <Link
        href="/admin/rubrics"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> All rubrics
      </Link>

      <div className="mb-6">
        <h1 className="flex flex-wrap items-center gap-3 text-2xl font-semibold tracking-tight">
          {rubric.name}
          <Badge variant={rubric.status === "published" ? "success" : "outline"}>
            {rubric.status}
          </Badge>
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {rubric.rubric_version_id} · {rubric.response_format} {rubric.scale_min}–
          {rubric.scale_max} · {items.length} items
        </p>
        {/* The rubric's own statement of what it is for. It has always been in the seed
            file and has never been on a screen. */}
        {rubric.scope ? (
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {rubric.scope}
          </p>
        ) : null}
      </div>

      <div role="tablist" aria-label="How to read this rubric" className="mb-6 inline-flex rounded-md border p-1">
        <ViewTab current={view} value="items" onSelect={setView}>
          Items
        </ViewTab>
        <ViewTab current={view} value="preview" onSelect={setView}>
          Preview
        </ViewTab>
      </div>

      {view === "items" ? (
        <ItemsView items={items} />
      ) : (
        <PreviewView rubric={rubric} items={items} />
      )}
    </div>
  );
}

function ViewTab({
  current,
  value,
  onSelect,
  children,
}: {
  current: View;
  value: View;
  onSelect: (v: View) => void;
  children: React.ReactNode;
}) {
  const selected = current === value;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={selected}
      onClick={() => onSelect(value)}
      className={cn(
        "rounded px-4 py-1.5 text-sm font-medium transition-colors",
        selected ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function ItemsView({ items }: { items: RubricCriterion[] }) {
  return (
    <Card>
      <CardContent className="divide-y p-0">
        {items.map((item, index) => (
          <div key={item.criterion_id} className="p-5">
            <div className="flex gap-4">
              <span className="w-6 shrink-0 pt-0.5 text-sm font-medium tabular-nums text-muted-foreground">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                {/* The id is the tooltip, as on the instruments page: the language here is
                    the statements, and ids are for lineage and dispute paths. */}
                <p className="font-medium" title={item.criterion_id}>
                  {item.prompt}
                </p>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {item.dimension} · elicits {item.qualities.join(", ") || "—"} · grounded in{" "}
                  {item.grounded_in.join(", ") || "—"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {/* Why an expert may never be shown this item at all (ADR-0053). */}
                  {item.required_data.length > 0
                    ? `asked only of a course that declares ${item.required_data.join(", ")}`
                    : "asked of every course"}
                </p>
                {item.guidance ? (
                  <details className="group mt-3">
                    <summary className="cursor-pointer text-xs font-medium text-primary hover:underline">
                      What agreeing means
                    </summary>
                    <p className="mt-1.5 rounded-md bg-muted/60 p-3 text-sm text-muted-foreground">
                      {item.guidance}
                    </p>
                  </details>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/**
 * The evaluator's right rail, reproduced at its real width. The form is not full-width in
 * the app — it sits in a 400/460px column beside the course — and a preview any wider would
 * misrepresent the one thing somebody comes here to check.
 */
function PreviewView({
  rubric,
  items,
}: {
  rubric: { scale_min: number; scale_max: number; response_format: string };
  items: RubricCriterion[];
}) {
  return (
    <div>
      <div className="mb-4 max-w-2xl space-y-2 rounded-md border border-dashed bg-muted/40 p-4 text-xs text-muted-foreground">
        <p>
          <span className="font-medium text-foreground">Nothing here is recorded.</span> This is
          the form an expert answers, in the column it appears in — they read the course beside
          it, in the other half of the screen. Click through the scale freely.
        </p>
        <p>
          Every item is shown. A real assignment hides the ones the course it is about declares
          nothing for, so an expert may see fewer than these {items.length} — and, for the ones
          that rest on a declaration, it shows them what the course declares. There is no course
          here, so neither happens.
        </p>
      </div>

      <div className="w-full max-w-[460px]">
        <CollapsibleSection title="Score" badge={`${items.length} items`}>
          <ScoreForm
            preview
            criteria={items}
            scaleMin={rubric.scale_min}
            scaleMax={rubric.scale_max}
            responseFormat={rubric.response_format}
          />
        </CollapsibleSection>
      </div>
    </div>
  );
}
