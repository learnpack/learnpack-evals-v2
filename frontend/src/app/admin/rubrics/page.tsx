"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCampaigns, useReferenceInstruments } from "@/lib/api/hooks";

export default function RubricsPage() {
  const { data: rubrics, isLoading, error } = useReferenceInstruments();
  // Read from the campaigns the console already lists, and counted here rather than asked of
  // the backend: it is a question about campaigns, and Orchestration is where it is answered.
  const { data: campaigns } = useCampaigns();

  const pinnedBy = (rubricVersionId: string) =>
    (campaigns ?? []).filter((c) => c.instrument_version_id === rubricVersionId).length;

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Rubrics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          The human reference instrument: what a subject-matter expert is asked, directly about
          the qualities of a course, by taking it. Not the evidential argument under{" "}
          <Link href="/admin/instruments" className="underline underline-offset-2">
            Instruments
          </Link>{" "}
          — that one is executed against a profile; this one is answered by a person. Authoring
          is file-based (<code>app.cli seed --file</code>).
        </p>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !rubrics || rubrics.length === 0 ? (
        <EmptyState
          title="No published rubric"
          hint="Install one with app.cli seed --file <rubric.json>."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rubric</TableHead>
                  <TableHead>Items</TableHead>
                  <TableHead>Answered as</TableHead>
                  <TableHead>In use</TableHead>
                  <TableHead className="text-right">Content</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rubrics.map((r) => {
                  const campaignCount = pinnedBy(r.rubric_version_id);
                  return (
                    <TableRow key={r.rubric_version_id}>
                      <TableCell>
                        <div className="font-medium">{r.name}</div>
                        <div className="text-xs text-muted-foreground">{r.rubric_version_id}</div>
                      </TableCell>
                      <TableCell>{r.item_count}</TableCell>
                      <TableCell className="text-sm">
                        {r.response_format} {r.scale_min}–{r.scale_max}
                      </TableCell>
                      <TableCell>
                        {/* Plain text, not a link: there is no campaign filter to link to,
                            and a link that lands on an unfiltered list is a broken promise. */}
                        {campaignCount === 0 ? (
                          <span className="text-sm text-muted-foreground">no campaigns</span>
                        ) : (
                          <Badge variant="secondary">
                            {campaignCount} campaign{campaignCount === 1 ? "" : "s"}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link
                          href={`/admin/rubrics/${r.rubric_version_id}`}
                          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                        >
                          Open <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
