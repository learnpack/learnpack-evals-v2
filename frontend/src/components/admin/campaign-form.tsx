"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState, Spinner } from "@/components/ui/states";
import {
  useContents,
  useCreateCampaign,
  useDatasets,
  useReferenceInstruments,
} from "@/lib/api/hooks";
import { ApiError } from "@/lib/api/client";
import { latestVersion } from "@/lib/datasets";
import type { Uuid } from "@/lib/api/types";

export function CampaignForm({ onDone }: { onDone: () => void }) {
  const { data: contents } = useContents();
  const { data: datasets, isLoading: loadingDatasets } = useDatasets();
  const { data: instruments, isLoading: loadingInstruments } = useReferenceInstruments();
  const createCampaign = useCreateCampaign();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instrument, setInstrument] = useState("");
  const [required, setRequired] = useState(2);
  const [datasetId, setDatasetId] = useState("");
  const [versionId, setVersionId] = useState("");

  // Preselected only when there is nothing to choose between. With several, the field stays
  // empty and submit refuses: a campaign opened against a default nobody looked at is the
  // hardcoded constant this replaces, wearing a dropdown (ADR-0056).
  useEffect(() => {
    if (instruments?.length === 1) setInstrument(instruments[0].rubric_version_id);
  }, [instruments]);

  const dataset = datasets?.find((d) => d.dataset_id === datasetId);

  // The latest version is a convenience, and it is **resolved here**: what the campaign
  // records is the id, never "whichever was newest at the time" (ADR-0058 §5).
  useEffect(() => {
    if (!dataset) {
      setVersionId("");
      return;
    }
    setVersionId(latestVersion(dataset)?.version_id ?? "");
  }, [dataset]);

  const version = dataset?.versions.find((v) => v.version_id === versionId);
  const courseLabel = (id: Uuid) => {
    const course = contents?.find((c) => c.content_id === id);
    return course ? `${course.external_id} · v${course.version}` : id.slice(0, 8);
  };

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      toast.error("Give the campaign a name.");
      return;
    }
    if (!instrument) {
      toast.error("Choose the instrument this campaign evaluates against.");
      return;
    }
    if (!versionId) {
      toast.error("Choose the dataset version this campaign runs on.");
      return;
    }
    createCampaign.mutate(
      {
        name: name.trim(),
        description: description.trim() || null,
        instrument_version_id: instrument,
        required_evaluations_per_content: required,
        dataset_version_id: versionId,
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
        <Label htmlFor="campaign-instrument">Instrument</Label>
        {loadingInstruments ? (
          <Spinner />
        ) : !instruments || instruments.length === 0 ? (
          <EmptyState
            title="No published instrument"
            hint="A campaign is evaluated against a published reference instrument. Seed or publish one first."
          />
        ) : (
          <Select
            id="campaign-instrument"
            value={instrument}
            onChange={(e) => setInstrument(e.target.value)}
          >
            <option value="">Choose an instrument…</option>
            {instruments.map((i) => (
              <option key={i.rubric_version_id} value={i.rubric_version_id}>
                {i.name} · {i.version} · {i.criterion_count} items
              </option>
            ))}
          </Select>
        )}
        <p className="text-xs text-muted-foreground">
          Fixed when the campaign opens: the answers it collects are answers to this
          version&apos;s items.
        </p>
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

      <div className="space-y-1.5">
        <Label htmlFor="campaign-dataset">Courses</Label>
        {loadingDatasets ? (
          <Spinner />
        ) : !datasets || datasets.length === 0 ? (
          <EmptyState
            title="No datasets yet"
            hint="A campaign runs on a named set of courses. Declare one first."
          />
        ) : (
          <div className="space-y-2">
            <Select
              id="campaign-dataset"
              value={datasetId}
              onChange={(e) => setDatasetId(e.target.value)}
            >
              <option value="">Choose a dataset…</option>
              {datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.name} · {latestVersion(d)?.content_ids.length ?? 0} courses
                </option>
              ))}
            </Select>

            {dataset ? (
              <Select
                aria-label="Dataset version"
                value={versionId}
                onChange={(e) => setVersionId(e.target.value)}
              >
                {[...dataset.versions].reverse().map((v) => (
                  <option key={v.version_id} value={v.version_id}>
                    v{v.ordinal} · {v.content_ids.length} courses · {v.note}
                  </option>
                ))}
              </Select>
            ) : null}
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          The version is copied when the campaign opens, so editing the set afterwards leaves
          this campaign where it is.{" "}
          <Link href="/admin/datasets" className="underline">
            Manage datasets
          </Link>
        </p>
      </div>

      {version ? (
        <div className="space-y-1.5">
          <Label>These {version.content_ids.length} courses</Label>
          <ul className="max-h-40 space-y-0.5 overflow-y-auto rounded-md border p-2 text-sm">
            {version.content_ids.map((id) => {
              const course = contents?.find((c) => c.content_id === id);
              return (
                // Marked, never hidden (ADR-0028): a course with no deployed instance is
                // still an evaluand. What it cannot take is a human assignment, and that
                // refusal lives in AssignForm.
                <li key={id} className="truncate">
                  {courseLabel(id)}
                  {course && !course.consumable_url ? (
                    <span className="text-xs text-muted-foreground"> · not deployed</span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <div className="flex justify-end gap-2 pt-1">
        <Button
          type="button"
          variant="outline"
          onClick={onDone}
          disabled={createCampaign.isPending}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={
            createCampaign.isPending ||
            !instruments ||
            instruments.length === 0 ||
            !datasets ||
            datasets.length === 0
          }
        >
          {createCampaign.isPending ? <Spinner /> : null}
          Open campaign
        </Button>
      </div>
    </form>
  );
}
