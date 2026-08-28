"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { useRenameDataset } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { DatasetResponse } from "@/lib/api/types";

/**
 * The label, edited whole: both fields are prefilled and both are sent, so what is left blank
 * here is cleared there. It mints no version — the set did not move (ADR-0058 §2).
 */
export function RenameDatasetForm({
  dataset,
  onDone,
}: {
  dataset: DatasetResponse;
  onDone: () => void;
}) {
  const rename = useRenameDataset(dataset.dataset_id);
  const [name, setName] = useState(dataset.name);
  const [description, setDescription] = useState(dataset.description ?? "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("A dataset needs a name.");
      return;
    }
    rename.mutate(
      { name: name.trim(), description: description.trim() || null },
      {
        onSuccess: () => {
          toast.success("Dataset renamed.");
          onDone();
        },
        onError: (err) => {
          const e = err as ApiError;
          toast.error("Could not rename the dataset.", { description: e.message });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="rename-dataset-name">Name</Label>
        <Input
          id="rename-dataset-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="rename-dataset-description">Description (optional)</Label>
        <Textarea
          id="rename-dataset-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="outline" onClick={onDone} disabled={rename.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={rename.isPending}>
          {rename.isPending ? <Spinner /> : null}
          Save
        </Button>
      </div>
    </form>
  );
}
