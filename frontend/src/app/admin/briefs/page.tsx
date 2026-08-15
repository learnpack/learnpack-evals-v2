"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useBriefs, useContents, useCreateBrief } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";

export default function BriefsPage() {
  const { data: briefs, isLoading, error } = useBriefs();
  const { data: contents } = useContents();
  const [creating, setCreating] = useState(false);

  // What each commission brought. It is the fact that makes this list mean something —
  // and the same grouping the study form does to pair versions over the same work.
  const coursesPerBrief = useMemo(() => {
    const counted = new Map<string, number>();
    for (const content of contents ?? []) {
      if (content.brief_id) counted.set(content.brief_id, (counted.get(content.brief_id) ?? 0) + 1);
    }
    return counted;
  }, [contents]);

  return (
    <div className="max-w-5xl">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Briefs</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            The assignment a course was generated from, and the key that pairs generator
            versions over the same work. They <span className="font-medium text-foreground">
            arrive on their own</span> when a course is registered whose package carries its
            commission (ADR-0022) — a format with no intake for it registers the brief absent.
          </p>
        </div>
        {/* Secondary on purpose: typing one by hand is the rare case, for a course whose
            package never carried its commission. */}
        <Button variant="outline" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> Add one by hand
        </Button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !briefs || briefs.length === 0 ? (
        <EmptyState
          title="No briefs yet"
          hint="They appear as soon as you register a course whose package declares what it was asked to make."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Brief</TableHead>
                  <TableHead className="w-40">Courses</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {briefs.map((b) => {
                  const courses = coursesPerBrief.get(b.brief_id) ?? 0;
                  return (
                    <TableRow key={b.brief_id}>
                      <TableCell className="max-w-xl truncate font-medium" title={b.brief}>
                        {b.brief}
                      </TableCell>
                      {/* Zero is worth showing: a commission nothing answers pairs nothing,
                          and it is the one row on this page that asks a question. */}
                      <TableCell className="tabular-nums text-muted-foreground">
                        {contents === undefined
                          ? "—"
                          : courses === 0
                            ? "none yet"
                            : `${courses} ${courses === 1 ? "course" : "courses"}`}
                      </TableCell>
                    </TableRow>
                  );
                })}
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
