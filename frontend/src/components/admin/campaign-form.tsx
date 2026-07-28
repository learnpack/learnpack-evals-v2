"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, Spinner } from "@/components/ui/states";
import { useContents, useCreateCampaign } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { METADATA_KEYS, RUBRIC_VERSION_ID } from "@/lib/constants";
import { cn } from "@/lib/utils";

export function CampaignForm({ onDone }: { onDone: () => void }) {
  const { data: contents } = useContents();
  const createCampaign = useCreateCampaign();

  const [required, setRequired] = useState(2);
  const [contentIds, setContentIds] = useState<string[]>([]);
  const [metadataView, setMetadataView] = useState<string[]>(
    METADATA_KEYS.map((k) => k.key), // show everything by default
  );

  function toggle(list: string[], setList: (v: string[]) => void, value: string) {
    setList(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (contentIds.length === 0) {
      toast.error("Select at least one course.");
      return;
    }
    createCampaign.mutate(
      {
        rubric_version_id: RUBRIC_VERSION_ID,
        required_evaluations_per_content: required,
        content_ids: contentIds,
        metadata_view: metadataView,
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
              <CheckRow
                key={c.content_id}
                checked={contentIds.includes(c.content_id)}
                onChange={() => toggle(contentIds, setContentIds, c.content_id)}
                label={`${c.external_id} · v${c.version}`}
              />
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <Label>Metadata evaluators can see</Label>
        <div className="space-y-1 rounded-md border p-2">
          {METADATA_KEYS.map((k) => (
            <CheckRow
              key={k.key}
              checked={metadataView.includes(k.key)}
              onChange={() => toggle(metadataView, setMetadataView, k.key)}
              label={k.label}
            />
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Unchecked keys stay hidden from the evaluator&apos;s view.
        </p>
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
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent",
      )}
    >
      <input type="checkbox" checked={checked} onChange={onChange} className="h-4 w-4" />
      {label}
    </label>
  );
}
