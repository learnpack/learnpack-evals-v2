"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProgressReport } from "@/lib/api/hooks";

/** Who is carrying what, across every campaign.
 *
 *  The one question that survives leaving a campaign (ADR-0060 §6). It is about **people** —
 *  who is overloaded, who abandoned, who has not opened anything in a fortnight — and with
 *  25 experts over several rounds it is asked exactly this way, without a campaign in the
 *  way. What a course scored used to sit beside it and no longer does: that is a
 *  measurement, and it is read inside the campaign that fixed the instrument.
 */
export default function WorkloadPage() {
  const { data, isLoading, error } = useProgressReport();

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight">Evaluator workload</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Assignments across every campaign. For what a round found, open its campaign&apos;s
        report.
      </p>

      {isLoading ? (
        <div className="mt-6">
          <LoadingState />
        </div>
      ) : error ? (
        <div className="mt-6">
          <ErrorState message={(error as Error).message} />
        </div>
      ) : !data ? null : (
        <div className="mt-6 space-y-6">
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
      )}
    </div>
  );
}
