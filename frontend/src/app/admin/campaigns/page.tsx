"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CampaignForm } from "@/components/admin/campaign-form";
import { useCampaigns } from "@/lib/api/hooks";

function statusVariant(status: string) {
  if (status === "open") return "success" as const;
  if (status === "closed") return "secondary" as const;
  return "outline" as const;
}

export default function CampaignsPage() {
  const { data: campaigns, isLoading, error } = useCampaigns();
  const [creating, setCreating] = useState(false);

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Campaigns</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Each campaign evaluates a set of courses against the pedagogical rubric.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> New campaign
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !campaigns || campaigns.length === 0 ? (
        <EmptyState title="No campaigns yet" hint="Open a campaign to assign courses to evaluators." />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campaign</TableHead>
                  <TableHead>Courses</TableHead>
                  <TableHead>Quorum</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Manage</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaigns.map((c) => (
                  <TableRow key={c.campaign_id}>
                    <TableCell className="font-medium">{c.campaign_id.slice(0, 8)}</TableCell>
                    <TableCell>{c.content_ids.length}</TableCell>
                    <TableCell>{c.required_evaluations_per_content}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/admin/campaigns/${c.campaign_id}`}
                        className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                      >
                        Open <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog
        open={creating}
        onClose={() => setCreating(false)}
        title="Open a campaign"
        description="Pick the courses and the evaluation quorum. It opens immediately."
      >
        <CampaignForm onDone={() => setCreating(false)} />
      </Dialog>
    </div>
  );
}
