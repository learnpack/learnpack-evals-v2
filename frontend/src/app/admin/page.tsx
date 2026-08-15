"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Play, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, LoadingState } from "@/components/ui/states";
import { StudyStatusBadge } from "@/components/admin/study-status";
import { useContents, useGeneratorVersions, useStudies } from "@/lib/api/hooks";
import { groupByVersion, measuredVersionIds, type VersionGroup } from "@/lib/versions";
import type { StudyResponse } from "@/lib/api/types";

/** How many rounds the front page carries. Enough to see where things stand, few enough
 *  that the list stays a glance rather than a second Studies page. */
const RECENT_ROUNDS = 5;

/**
 * The console's front page answers one question: what is left to do?
 *
 * It used to be seven cards linking to the same pages as the nav — a toll of one click that
 * carried no information. The nav groups those destinations now, so this is free to say the
 * one thing only the console knows: which registered versions nobody has measured, and how
 * the last rounds ended.
 */
export default function AdminHome() {
  const router = useRouter();
  const studies = useStudies();
  const contents = useContents();
  const generatorVersions = useGeneratorVersions();

  const loading = studies.isLoading || contents.isLoading || generatorVersions.isLoading;

  const unmeasured = useMemo(() => {
    const measured = measuredVersionIds(studies.data ?? [], contents.data ?? []);
    return groupByVersion(contents.data ?? [], generatorVersions.data ?? []).filter(
      // A version with no courses is not unmeasured, it is unused — putting it here would
      // be permanent noise on the front page. `unknown` can never be measured at all.
      (group) => group.version !== null && !measured.has(group.version.generator_version_id),
    );
  }, [studies.data, contents.data, generatorVersions.data]);

  const recent = (studies.data ?? []).slice(0, RECENT_ROUNDS);

  return (
    <div className="max-w-4xl space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin console</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Register what a generator version made, measure it against an instrument, read
            what came back.
          </p>
        </div>
        <Button className="shrink-0" onClick={() => router.push("/admin/studies/new")}>
          <Plus className="h-4 w-4" /> New study
        </Button>
      </div>

      {loading ? (
        <LoadingState />
      ) : (
        <>
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Versions nobody has measured</h2>
            {unmeasured.length === 0 ? (
              <EmptyState
                title="Every registered version has been measured"
                hint="Register courses from a new version and it will show up here."
              />
            ) : (
              <div className="space-y-2">
                {unmeasured.map((group) => (
                  <UnmeasuredRow key={group.key} group={group} />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="text-sm font-medium">Last rounds</h2>
              <Link
                href="/admin/studies"
                className="text-xs text-muted-foreground hover:underline"
              >
                All studies
              </Link>
            </div>
            {recent.length === 0 ? (
              <EmptyState
                title="No rounds yet"
                hint="A round is an instrument, a judge and a set of courses."
              />
            ) : (
              <Card>
                <CardContent className="divide-y p-0">
                  {/* Newest first, as the API answers it — not re-sorted here, for the same
                      reason the studies list says so: two places deciding one order is how
                      they come to disagree. */}
                  {recent.map((study) => (
                    <RoundRow key={study.study_id} study={study} />
                  ))}
                </CardContent>
              </Card>
            )}
          </section>
        </>
      )}
    </div>
  );
}

/** One version waiting to be measured, and the act that measures it — the same link the
 *  course list carries, so there is one way a round gets composed. */
function UnmeasuredRow({ group }: { group: VersionGroup }) {
  const router = useRouter();
  const commissions = group.briefIds.size;

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="min-w-0">
          <p className="font-medium">
            {group.version!.name} {group.version!.version}
          </p>
          <p className="text-sm tabular-nums text-muted-foreground">
            {group.courses.length} {group.courses.length === 1 ? "course" : "courses"} ·{" "}
            {commissions} {commissions === 1 ? "commission" : "commissions"} ·{" "}
            {group.formats.join(", ")}
          </p>
        </div>
        <Button
          className="shrink-0"
          disabled={commissions === 0}
          title={
            commissions === 0
              ? "No commission recorded for these courses, so there is no dataset to compose."
              : undefined
          }
          onClick={() => router.push(`/admin/studies/new?versions=${group.key}`)}
        >
          <Play className="h-3.5 w-3.5" /> Measure
        </Button>
      </CardContent>
    </Card>
  );
}

function RoundRow({ study }: { study: StudyResponse }) {
  return (
    <Link
      href={`/admin/studies/${study.study_id}`}
      className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 hover:bg-accent/40"
    >
      <span className="min-w-0">
        <span className="block truncate font-medium">{study.name}</span>
        <span className="block text-xs tabular-nums text-muted-foreground">
          {study.content_ids.length}{" "}
          {study.content_ids.length === 1 ? "course" : "courses"} ·{" "}
          {study.brief_ids.length}{" "}
          {study.brief_ids.length === 1 ? "commission" : "commissions"}
          {study.opened_at
            ? ` · started ${new Date(study.opened_at).toLocaleDateString()}`
            : ""}
        </span>
      </span>
      <StudyStatusBadge status={study.status} />
    </Link>
  );
}
