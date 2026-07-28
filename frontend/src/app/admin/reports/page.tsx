"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useProgressReport, useScoresReport } from "@/lib/api/hooks";
import type { ContentScores } from "@/lib/api/types";

const TABS = ["Scores", "Progress"] as const;

export default function ReportsPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Scores");

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Aggregated scores, inter-rater agreement and progress.
      </p>

      <div className="mt-6 mb-6 inline-flex rounded-lg border bg-muted/40 p-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
              tab === t ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Scores" ? <ScoresReport /> : <ProgressReport />}
    </div>
  );
}

const fmt = (n: number | null, digits = 2) => (n === null ? "—" : n.toFixed(digits));

function ScoresReport() {
  const { data, isLoading, error } = useScoresReport();

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  const hasData = data.contents.some((c) => c.evaluator_count > 0);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Global average" value={fmt(data.global_average)} />
        <Stat label="Courses" value={String(data.contents.length)} />
        <Stat label="Evaluators" value={String(data.assessors.length)} />
      </div>

      {!hasData ? (
        <EmptyState title="No evaluations submitted yet" hint="Scores appear once evaluators submit." />
      ) : (
        data.contents.map((content) => <ContentCard key={content.content_id} content={content} />)
      )}

      <Card>
        <CardHeader>
          <CardTitle>Per-evaluator averages</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Evaluator</TableHead>
                <TableHead>Evaluations</TableHead>
                <TableHead>Average</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.assessors.map((a) => (
                <TableRow key={a.assessor_id}>
                  <TableCell className="font-medium">
                    {a.display_name ?? a.email ?? a.assessor_id.slice(0, 8)}
                  </TableCell>
                  <TableCell>{a.evaluation_count}</TableCell>
                  <TableCell>{fmt(a.average)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function ContentCard({ content }: { content: ContentScores }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>{content.external_id}</CardTitle>
          <div className="flex items-center gap-2 text-sm">
            <Badge variant="secondary">{content.evaluator_count} raters</Badge>
            <span className="font-semibold">avg {fmt(content.average)}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {content.criteria.length === 0 ? (
          <p className="px-6 pb-6 text-sm text-muted-foreground">No submitted scores.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Criterion</TableHead>
                <TableHead>Average</TableHead>
                <TableHead>Std dev</TableHead>
                <TableHead>Mean pairwise Δ</TableHead>
                <TableHead>Exact agreement</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {content.criteria.map((c) => (
                <TableRow key={c.criterion_id}>
                  <TableCell className="font-medium">{c.criterion_id}</TableCell>
                  <TableCell>{fmt(c.average)}</TableCell>
                  <TableCell>{fmt(c.dispersion.stdev)}</TableCell>
                  <TableCell>{fmt(c.dispersion.mean_pairwise_abs_diff)}</TableCell>
                  <TableCell>
                    {c.dispersion.exact_agreement_pct === null
                      ? "—"
                      : `${c.dispersion.exact_agreement_pct.toFixed(0)}%`}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function ProgressReport() {
  const { data, isLoading, error } = useProgressReport();

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>By evaluator</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Evaluator</TableHead>
                <TableHead>Pending</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Cancelled</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.by_assessor.map((a) => (
                <TableRow key={a.assessor_id}>
                  <TableCell className="font-medium">
                    {a.display_name ?? a.assessor_id.slice(0, 8)}
                  </TableCell>
                  <TableCell>{a.counts.pending}</TableCell>
                  <TableCell>{a.counts.submitted}</TableCell>
                  <TableCell>{a.counts.cancelled}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>By course</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Course</TableHead>
                <TableHead>Pending</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Cancelled</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.by_content.map((c) => (
                <TableRow key={c.content_id}>
                  <TableCell className="font-medium">{c.external_id}</TableCell>
                  <TableCell>{c.counts.pending}</TableCell>
                  <TableCell>{c.counts.submitted}</TableCell>
                  <TableCell>{c.counts.cancelled}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="py-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}
