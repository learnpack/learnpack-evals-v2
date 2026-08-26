"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/states";
import { useRenameCampaign } from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import type { CampaignResponse } from "@/lib/api/types";

/**
 * The label, edited whole (ADR-0055): both fields are prefilled and both are sent, so what
 * is left blank here is cleared there. A campaign renames in any status, closed included.
 */
export function RenameCampaignForm({
  campaign,
  onDone,
}: {
  campaign: CampaignResponse;
  onDone: () => void;
}) {
  const rename = useRenameCampaign(campaign.campaign_id);
  const [name, setName] = useState(campaign.name);
  const [description, setDescription] = useState(campaign.description ?? "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("A campaign needs a name.");
      return;
    }
    rename.mutate(
      { name: name.trim(), description: description.trim() || null },
      {
        onSuccess: () => {
          toast.success("Campaign renamed.");
          onDone();
        },
        onError: (err) => {
          const e = err as ApiError;
          toast.error("Could not rename the campaign.", { description: e.message });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="rename-campaign-name">Name</Label>
        <Input
          id="rename-campaign-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="rename-campaign-description">Description (optional)</Label>
        <Textarea
          id="rename-campaign-description"
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
