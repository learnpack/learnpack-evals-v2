"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState, Spinner } from "@/components/ui/states";
import { useContents, useCreateCampaign } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { INSTRUMENT_VERSION_ID } from "@/lib/constants";
import { cn } from "@/lib/utils";

export function CampaignForm({ onDone }: { onDone: () => void }) {
  const { data: contents } = useContents();
  const createCampaign = useCreateCampaign();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [required, setRequired] = useState(2);
  const [contentIds, setContentIds] = useState<string[]>([]);

  function toggle(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Give the campaign a name.");
      return;
    }
    if (contentIds.length === 0) {
      toast.error("Select at least one course.");
      return;
    }
    createCampaign.mutate(
      {
        name: name.trim(),
        description: description.trim() || null,
        instrument_version_id: INSTRUMENT_VERSION_ID,
        required_evaluations_per_content: required,
        content_ids: contentIds,
      },
      {
        onSuccess: () => {
          toast.success("Campaign opened.");
          onDone();
        },
        onError: (err) => {
          const e = err as ApiError;
          toast.error("Could not open the campaign.", { description: e.message });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="campaign-name">Name</Label>
        <Input
          id="campaign-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="First reference campaign"
          autoFocus
        />
        <p className="text-xs text-muted-foreground">
          How this campaign is told apart from the next one. It can be corrected later.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="campaign-description">Description (optional)</Label>
        <Textarea
          id="campaign-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
      </div>

      <div className="space-y-1.5">
        <Label>Evaluations required per course</Label>
        <Input
          type="number"
          min={1}
          value={required}
          onChange={(e) => setRequired(Math.max(1, Number(e.target.value)))}
          className="w-32"
        />
        <p className="text-xs text-muted-foreground">
          The quorum: a course is complete once this many evaluators have submitted.
        </p>
      </div>

      <div className="space-y-2">
        <Label>Courses in this campaign</Label>
        {!contents || contents.length === 0 ? (
          <EmptyState title="No courses" hint="Register a course first." />
        ) : (
          <div className="max-h-52 space-y-1 overflow-y-auto rounded-md border p-2">
            {contents.map((c) => (
              // Marked, never hidden (ADR-0028): a campaign is a set of evaluands, and a
              // course with no deployed instance is still one for the automated path. What
              // it cannot take is a human assignment — that refusal lives in AssignForm.
              <CheckRow
                key={c.content_id}
                checked={contentIds.includes(c.content_id)}
                onChange={() => toggle(contentIds, setContentIds, c.content_id)}
                label={`${c.external_id} · v${c.version}`}
                hint={c.consumable_url ? undefined : "not deployed"}
              />
            ))}
          </div>
        )}
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="outline" onClick={onDone} disabled={createCampaign.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={createCampaign.isPending}>
          {createCampaign.isPending ? <Spinner /> : null}
          Open campaign
        </Button>
      </div>
    </form>
  );
}

function CheckRow({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
  hint?: string;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent",
      )}
    >
      <input type="checkbox" checked={checked} onChange={onChange} className="h-4 w-4" />
      {label}
      {hint ? <span className="text-xs text-muted-foreground">· {hint}</span> : null}
    </label>
  );
}
