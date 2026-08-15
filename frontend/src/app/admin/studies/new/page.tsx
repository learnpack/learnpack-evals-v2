"use client";

import { Suspense, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { StudyForm } from "@/components/admin/study-form";
import { LoadingState } from "@/components/ui/states";
import { useContents, useGeneratorVersions } from "@/lib/api/hooks";
import type { ContentResponse, GeneratorVersionResponse, Uuid } from "@/lib/api/types";

/** `useSearchParams` needs a Suspense boundary or `next build` refuses to prerender the
 *  page — and CI runs only `tsc`, so this is the one thing here that no check would catch
 *  before a deploy did. */
export default function NewStudyPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <NewStudy />
    </Suspense>
  );
}

/** Creating a study is filling in the form once. The same form serves a draft that already
 *  has an id — see the study's own page — because they were never two screens.
 *
 *  Courses links here with the versions it was looking at, and this is where that link is
 *  translated: the URL carries the versions and nothing else, and the name and the
 *  commissions are derived from them. Composition rules live in one place, and it is not a
 *  query string. */
function NewStudy() {
  const params = useSearchParams();
  const contents = useContents();
  const generatorVersions = useGeneratorVersions();

  // Read at mount and never again — after that the fields belong to whoever is typing.
  const requested = useMemo(
    () => (params.get("versions") ?? "").split(",").filter(Boolean) as Uuid[],
    [params],
  );

  const named = requested.length > 0;
  // The form reads its initial values ONCE, in `useState` initializers, so mounting it
  // before the courses arrive would freeze the commissions at none and lose the prefill
  // with nothing to show for it.
  const waiting = named && (contents.data === undefined || generatorVersions.data === undefined);

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link
          href="/admin/studies"
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Studies
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">New study</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          A study is one round: an instrument, a judge and a set of courses. Everything here
          can change until the round starts.
        </p>
      </div>

      {waiting ? (
        <LoadingState label="Reading what those versions made…" />
      ) : (
        <StudyForm
          initialScope={named ? requested : undefined}
          initialName={named ? nameFor(requested, generatorVersions.data ?? []) : undefined}
          initialBriefIds={named ? commissionsOf(requested, contents.data ?? []) : undefined}
        />
      )}
    </div>
  );
}

/** What the round is about, as a sentence somebody will read in a report months later. */
function nameFor(versionIds: Uuid[], versions: GeneratorVersionResponse[]): string {
  const chosen = versionIds
    .map((id) => versions.find((version) => version.generator_version_id === id))
    .filter((version): version is GeneratorVersionResponse => version !== undefined);
  if (chosen.length === 0) return "";
  const [first, ...rest] = chosen;
  const lineage = rest.every((version) => version.name === first.name) ? `${first.name} ` : "";
  return `${lineage}${chosen.map((version) => version.version).join(" vs ")}`;
}

/**
 * Every commission these versions answered — the union, not the intersection.
 *
 * Intersecting would drop the unpaired ones in silence, and the form itself says including
 * them is legitimate: it is a comparison over fewer paired commissions. With the union its
 * per-version counts and its unpaired warning do the telling, instead of this function
 * deciding for somebody.
 */
function commissionsOf(versionIds: Uuid[], contents: ContentResponse[]): Uuid[] {
  const wanted = new Set<string>(versionIds);
  const briefs = new Set<Uuid>();
  for (const content of contents) {
    if (!content.brief_id || !content.generator_version_id) continue;
    if (wanted.has(content.generator_version_id)) briefs.add(content.brief_id);
  }
  return [...briefs];
}
