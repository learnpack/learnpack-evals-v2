"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { CoursePicker } from "@/components/admin/course-picker";
import { FormActions } from "@/components/admin/form-actions";
import { useContents, useDeclareDataset } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";

/**
 * Declare a named set and freeze its first version, in one act (ADR-0058 §1) — there is no
 * such thing here as a dataset with no version.
 *
 * A page rather than a dialog: composing a set is the longest errand in the console, and a
 * click outside a dialog would take forty chosen courses with it.
 */
export function DatasetForm() {
  const router = useRouter();
  const { data: courses } = useContents();
  const declareDataset = useDeclareDataset();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [note, setNote] = useState("");
  const [contentIds, setContentIds] = useState<string[]>([]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Give the set a name.");
      return;
    }
    if (!note.trim()) {
      toast.error("Say why this first version exists.");
      return;
    }
    if (contentIds.length === 0) {
      toast.error("Select at least one course.");
      return;
    }
    declareDataset.mutate(
      {
        name: name.trim(),
        description: description.trim() || null,
        note: note.trim(),
        content_ids: contentIds,
      },
      {
        onSuccess: (created) => {
          toast.success("Dataset declared at v1.");
          router.push(`/admin/datasets/${created.dataset_id}`);
        },
        onError: (err) => {
          const e = err as ApiError;
          toast.error("Could not declare the dataset.", { description: e.message });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="dataset-name">Name</Label>
          <Input
            id="dataset-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="SME reference set"
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            How this set is told apart from the next one. It can be corrected later, and
            correcting it changes no version.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="dataset-note">Why this version exists</Label>
          <Input
            id="dataset-note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="The 40 courses of the first reference campaign"
          />
          <p className="text-xs text-muted-foreground">
            Required. Every version carries one: it is what tells a later reader why the numbers
            from an earlier round cannot be compared with the next.
          </p>
        </div>

        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="dataset-description">Description (optional)</Label>
          <Textarea
            id="dataset-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </div>
      </div>

      <CoursePicker courses={courses} selected={contentIds} onChange={setContentIds} />

      <FormActions
        status={`${contentIds.length} ${contentIds.length === 1 ? "course" : "courses"} in this set`}
      >
        <Link href="/admin/datasets" className={buttonVariants({ variant: "outline" })}>
          Cancel
        </Link>
        <Button type="submit" disabled={declareDataset.isPending}>
          {declareDataset.isPending ? <Spinner /> : null}
          Declare set
        </Button>
      </FormActions>
    </form>
  );
}
