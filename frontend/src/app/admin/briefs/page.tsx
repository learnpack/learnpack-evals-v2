"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBriefs, useCreateBrief } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";

export default function BriefsPage() {
  const { data: briefs, isLoading, error } = useBriefs();
  const [creating, setCreating] = useState(false);

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Briefs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Generation assignments — the key of paired comparison between generator versions.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> Register brief
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !briefs || briefs.length === 0 ? (
        <EmptyState
          title="No briefs yet"
          hint="Register the assignment a content was generated from to enable paired comparison."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Brief</TableHead>
                  <TableHead className="w-40">Id</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {briefs.map((b) => (
                  <TableRow key={b.brief_id}>
                    <TableCell className="max-w-xl truncate font-medium" title={b.brief}>
                      {b.brief}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {b.brief_id.slice(0, 8)}…
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
        title="Register a brief"
        description="The assignment given to the generator. Immutable once registered."
      >
        <BriefForm onDone={() => setCreating(false)} />
      </Dialog>
    </div>
  );
}

function BriefForm({ onDone }: { onDone: () => void }) {
  const createBrief = useCreateBrief();
  const [brief, setBrief] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    createBrief.mutate(
      { brief: brief.trim() },
      {
        onSuccess: () => {
          toast.success("Brief registered.");
          onDone();
        },
        onError: (err) =>
          toast.error("Could not register the brief.", {
            description: (err as ApiError).message,
          }),
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label>
          Brief <span className="text-destructive">*</span>
        </Label>
        <Textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={5}
          placeholder="An introductory course on Python loops for junior developers…"
          required
        />
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={createBrief.isPending}>
          {createBrief.isPending ? <Spinner /> : null}
          Register
        </Button>
      </div>
    </form>
  );
}
