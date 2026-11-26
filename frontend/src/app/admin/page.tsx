"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, LoadingState } from "@/components/ui/states";
import { StudyStatusBadge } from "@/components/admin/study-status";
import { useContents, useGeneratorVersions, useStudies } from "@/lib/api/hooks";
import { groupByVersion, measuredVersionIds, type VersionGroup } from "@/lib/versions";
import { IS_LOCAL_AUTH } from "@/lib/auth";
import type { StudyResponse } from "@/lib/api/types";

/** How many rounds the front page carries. Enough to see where things stand, few enough
 *  that the list stays a glance rather than a second Studies page. */
const RECENT_ROUNDS = 5;

/** The three things a person comes to the console to do, written from their side of the
 *  screen. The first one depends on the mode: importing from a folder exists only on a local
 *  setup, and a deployed console composes a study from courses already registered. */
const TASKS = [
  {
    title: "Evaluate a batch of courses",
    body: "Measure what one generator version produced, criterion by criterion, with the passage behind each verdict.",
    href: IS_LOCAL_AUTH ? "/admin/measure" : "/admin/studies/new",
    action: "Start",
  },
  {
    title: "Try one course",
    body: "See how a single course does against an instrument. Nothing is saved, so you can try as often as you like.",
    href: "/admin/calibration",
    action: "Pick a course",
  },
  {
    title: "Ask experts",
    body: "Have subject-matter experts rate courses, and check whether the automated verdicts follow them.",
    href: "/admin/campaigns",
    action: "Campaigns",
  },
];

/**
 * The console's front page answers two questions, in the order somebody arriving asks them:
 * what can I do here, and what is left to do?
 *
 * The first is the three tasks, because a reader who does not know the model yet cannot
 * start from the nav, which is a list of the things the model is made of. The second is what
 * only the console knows: which registered versions nobody has measured, and how the latest
 * studies ended.
 */
export default function AdminHome() {
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
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">What do you want to find out?</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            The instruments and assessors are already set up. Pick a task to start.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {TASKS.map((task, index) => (
            <Link
              key={task.title}
              href={task.href}
              className={
                index === 0
                  ? "flex flex-col gap-2 rounded-lg border border-primary/40 bg-primary/5 p-4 transition-colors hover:bg-primary/10"
                  : "flex flex-col gap-2 rounded-lg border bg-card p-4 transition-colors hover:bg-accent/40"
              }
            >
              <span className="font-medium">{task.title}</span>
              <span className="text-sm text-muted-foreground">{task.body}</span>
              <span className="mt-auto flex items-center gap-1 pt-1 text-sm font-medium text-primary">
                {task.action} <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </Link>
          ))}
        </div>
        <p className="text-sm text-muted-foreground">
          New here?{" "}
          <Link href="/admin/how-it-works" className="font-medium text-primary hover:underline">
            How evaluation works
          </Link>{" "}
          explains what is checked and how to read a result, in about three minutes.
        </p>
      </div>

      <h2 className="border-t pt-6 text-lg font-semibold tracking-tight">Pending</h2>

      {loading ? (
        <LoadingState />
      ) : (
        <>
          <section className="space-y-3">
            <h3 className="text-sm font-medium">Versions nobody has measured</h3>
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
              <h3 className="text-sm font-medium">Latest studies</h3>
              <Link
                href="/admin/studies"
                className="text-xs text-muted-foreground hover:underline"
              >
                All studies
              </Link>
            </div>
            {recent.length === 0 ? (
              <EmptyState
                title="No studies yet"
                hint="A study is an instrument, an assessor and a set of courses."
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
            {commissions} {commissions === 1 ? "brief" : "briefs"} ·{" "}
            {group.formats.join(", ")}
          </p>
        </div>
        <Button
          className="shrink-0"
          disabled={commissions === 0}
          title={
            commissions === 0
              ? "No brief recorded for these courses, so there is no dataset to compose."
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
          {study.brief_ids.length === 1 ? "brief" : "briefs"}
          {study.opened_at
            ? ` · started ${new Date(study.opened_at).toLocaleDateString()}`
            : ""}
        </span>
      </span>
      <StudyStatusBadge status={study.status} />
    </Link>
  );
}
