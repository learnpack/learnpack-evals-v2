"use client";

import Link from "next/link";
import { ReadPackagesButton } from "@/components/admin/read-packages-button";
import { useProfiles, useProfilingCapabilities } from "@/lib/api/hooks";
import type { Uuid } from "@/lib/api/types";
import {
  extractionStateOf,
  indexCapabilities,
  indexProfiles,
  summarizeExtraction,
} from "@/lib/extraction";

/** The lot the last batch touched, and how it went. */
export type Batch = { contentIds: Uuid[]; created: number; unchanged: number; failed: number };

/**
 * Whether the lot that just arrived came back readable.
 *
 * The bit that decides whether measuring it means anything: a course nobody could read
 * enters a round all the same and comes back with its criteria unassessed. It reads the
 * profiles the registrations just wrote, which is why both registration hooks invalidate
 * them.
 *
 * It offers the one act that belongs here — reading what came back unread — and not the
 * other. Accepting a format's extraction is judged over the profiles it produced, so it
 * stays on the workbench that renders them; from here it would be accepting blind.
 *
 * Shared by the two intakes rather than written twice: a lot of courses is a lot of courses
 * whether the list that named them was a folder tree or a file of URLs, and the question it
 * answers is the same one.
 */
export function BatchSummary({ batch, format }: { batch: Batch | null; format: string }) {
  const profiles = useProfiles();
  const capabilities = useProfilingCapabilities();

  if (batch === null || batch.contentIds.length === 0) return null;

  const known = profiles.data !== undefined && capabilities.data !== undefined;
  const index = indexCapabilities(capabilities.data);
  const byContent = indexProfiles(profiles.data, index);
  // The declared format, not the profile's: a course with no profile has no format to read
  // one off, and that is exactly the case whose reason the summary has to get right.
  const states = batch.contentIds.map((contentId) =>
    extractionStateOf(format, byContent.get(contentId), index),
  );
  const { read, notRead, failed } = summarizeExtraction(states);

  return (
    <div className="rounded-md border bg-muted/30 p-3 text-sm">
      <p className="tabular-nums">
        <span className="font-medium">
          {batch.contentIds.length} {batch.contentIds.length === 1 ? "course" : "courses"} in
          this lot
        </span>
        {" — "}
        {batch.created} newly registered, {batch.unchanged} already there
        {batch.failed > 0 ? (
          <span className="text-destructive">, {batch.failed} failed</span>
        ) : null}
        .
      </p>
      {known ? (
        <p className="mt-1 tabular-nums text-muted-foreground">
          {read} read
          {notRead > 0 ? <span className="text-amber-700"> · {notRead} not read</span> : null}
          {failed > 0 ? (
            <span className="text-destructive"> · {failed} could not be read</span>
          ) : null}
          {notRead > 0 || failed > 0 ? (
            <>
              {" · "}
              <Link href="/admin/profiles" className="text-primary hover:underline">
                see why in Profiles
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
      {known && notRead > 0 ? (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <ReadPackagesButton
            label={`Read ${notRead} now`}
            contentIds={batch.contentIds.filter(
              (contentId) => byContent.get(contentId) === undefined,
            )}
          />
          {notRead === batch.contentIds.length ? (
            <p className="text-xs text-amber-700">
              Nothing in this lot was read, so a round over it would answer nothing — usually
              because no one has accepted this format&apos;s extraction yet.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
