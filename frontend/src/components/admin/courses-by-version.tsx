"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { GitCompare, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { summarizeExtraction, type ExtractionState } from "@/lib/extraction";
import type { ContentResponse, GeneratorVersionResponse, Uuid } from "@/lib/api/types";

/**
 * The course list read as what it is: a set of generator versions and what each one made.
 *
 * A round measures a version, so this is the grain a person arrives with — «I generated
 * these with 2.0.1, is it better than 2.0.0» — and reconstructing it from a flat table by
 * filtering twice and then ticking commissions by hand is the errand this replaces.
 *
 * Nothing here is a new concept: a card is what the registered courses already say when
 * grouped by the version they declare.
 */
export function CoursesByVersion({
  contents,
  generatorVersions,
  extractionOf,
  onInspectUnknown,
}: {
  contents: ContentResponse[];
  generatorVersions: GeneratorVersionResponse[];
  extractionOf: (content: ContentResponse) => ExtractionState | null;
  /** Unknown-generator courses are attributed in the flat list, so the card sends you there. */
  onInspectUnknown: () => void;
}) {
  const [comparing, setComparing] = useState<VersionGroup | null>(null);

  const groups = useMemo(
    () => groupByVersion(contents, generatorVersions),
    [contents, generatorVersions],
  );

  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <VersionCard
          key={group.key}
          group={group}
          extractionOf={extractionOf}
          onCompare={() => setComparing(group)}
          onInspectUnknown={onInspectUnknown}
        />
      ))}

      <CompareDialog
        group={comparing}
        groups={groups}
        onClose={() => setComparing(null)}
      />
    </div>
  );
}

function VersionCard({
  group,
  extractionOf,
  onCompare,
  onInspectUnknown,
}: {
  group: VersionGroup;
  extractionOf: (content: ContentResponse) => ExtractionState | null;
  onCompare: () => void;
  onInspectUnknown: () => void;
}) {
  const router = useRouter();
  const states = group.courses.map(extractionOf);
  const known = !states.some((state) => state === null);
  const { failed, notRead, read } = summarizeExtraction(
    known ? (states as ExtractionState[]) : [],
  );

  const measurable = group.version !== null && group.briefIds.size > 0;

  return (
    <Card>
      <CardContent className="flex flex-wrap items-start justify-between gap-4 pt-6">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-medium">
              {group.version
                ? `${group.version.name} ${group.version.version}`
                : "Unknown generator"}
            </h2>
            {group.formats.map((format) => (
              <span key={format} className="text-xs text-muted-foreground">
                {format}
              </span>
            ))}
          </div>

          <p className="text-sm tabular-nums text-muted-foreground">
            {group.courses.length} {group.courses.length === 1 ? "course" : "courses"}
            {" · "}
            {group.briefIds.size}{" "}
            {group.briefIds.size === 1 ? "commission" : "commissions"}
            {known ? (
              <>
                {" · "}
                {read} read
                {notRead > 0 ? <span className="text-amber-700"> · {notRead} not read</span> : null}
                {failed > 0 ? (
                  <span className="text-destructive"> · {failed} could not be read</span>
                ) : null}
              </>
            ) : null}
          </p>

          {/* A course with no commission can never enter a round — the dataset is composed
              by brief — and nothing else in the console says so. */}
          {group.withoutBrief > 0 ? (
            <p className="text-xs text-amber-700">
              {group.withoutBrief} {group.withoutBrief === 1 ? "course has" : "courses have"} no
              commission recorded, so {group.withoutBrief === 1 ? "it cannot" : "they cannot"}{" "}
              enter a round.
            </p>
          ) : null}

          {group.version === null ? (
            <p className="text-xs text-muted-foreground">
              A round names the versions it measures, and these declare none — so they stay
              out of every one. Attribute a generator to bring them in.
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {group.version === null ? (
            <Button variant="outline" onClick={onInspectUnknown}>
              See them in the list
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={onCompare}>
                <GitCompare className="h-3.5 w-3.5" /> Compare with…
              </Button>
              <Button
                disabled={!measurable}
                title={
                  measurable
                    ? undefined
                    : "No commission recorded for these courses, so there is no dataset to compose."
                }
                onClick={() => router.push(`/admin/studies/new?versions=${group.key}`)}
              >
                <Play className="h-3.5 w-3.5" /> Measure this version
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Which version to compare against, and what the comparison would rest on.
 *
 * Every other version is offered, and the count of commissions both answered comes with it —
 * including zero, in amber. Hiding the zeroes would make the choice safe by making the fact
 * invisible, and a cross-format A/B is deliberately legitimate (ADR-0044 §7). This is the
 * earliest moment anyone can see that two versions are not answering the same work.
 */
function CompareDialog({
  group,
  groups,
  onClose,
}: {
  group: VersionGroup | null;
  groups: VersionGroup[];
  onClose: () => void;
}) {
  const router = useRouter();
  // A closed Dialog renders nothing, but React evaluates the children handed to it either
  // way — so the guard has to be here, not in the `open` prop.
  if (group === null) return null;

  const others = groups.filter((other) => other.version !== null && other.key !== group.key);

  return (
    <Dialog
      open
      onClose={onClose}
      title={
        group.version
          ? `Compare ${group.version.name} ${group.version.version} with…`
          : "Compare with…"
      }
      description="Two versions are comparable over the commissions both answered. The rest are still included — the round just says less about them."
    >
      {others.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No other generator version has courses registered yet.
        </p>
      ) : (
        <div className="space-y-2">
          {others.map((other) => {
            const shared = sharedCommissions(group, other);
            return (
              <button
                key={other.key}
                type="button"
                className="flex w-full items-center justify-between gap-3 rounded border p-2 text-left text-sm hover:bg-muted/50"
                onClick={() =>
                  router.push(`/admin/studies/new?versions=${group.key},${other.key}`)
                }
              >
                <span className="min-w-0">
                  <span className="block font-medium">
                    {other.version!.name} {other.version!.version}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {other.courses.length}{" "}
                    {other.courses.length === 1 ? "course" : "courses"} ·{" "}
                    {other.formats.join(", ")}
                  </span>
                </span>
                {shared === 0 ? (
                  <Badge variant="warning">no shared commissions</Badge>
                ) : (
                  <Badge variant="secondary">
                    {shared} shared {shared === 1 ? "commission" : "commissions"}
                  </Badge>
                )}
              </button>
            );
          })}
        </div>
      )}
    </Dialog>
  );
}

// -------------------------------------------------------------------------------- pure

/** One generator version and everything registered against it. `version: null` is the
 *  declared void of ADR-0024 — a group, but never something a round can measure. */
type VersionGroup = {
  /** The version id, or `unknown`. Doubles as the value the study link carries. */
  key: string;
  version: GeneratorVersionResponse | null;
  courses: ContentResponse[];
  /** The commissions it answered. A course with no brief is counted apart, not as one. */
  briefIds: Set<Uuid>;
  withoutBrief: number;
  formats: string[];
};

const UNKNOWN = "unknown";

function groupByVersion(
  contents: ContentResponse[],
  generatorVersions: GeneratorVersionResponse[],
): VersionGroup[] {
  const byKey = new Map<string, ContentResponse[]>();
  for (const content of contents) {
    const key = content.generator_version_id ?? UNKNOWN;
    byKey.set(key, [...(byKey.get(key) ?? []), content]);
  }

  const groups = [...byKey].map(([key, courses]) => ({
    key,
    version:
      generatorVersions.find((version) => version.generator_version_id === key) ?? null,
    courses,
    briefIds: new Set(
      courses.map((course) => course.brief_id).filter((id): id is Uuid => id !== null),
    ),
    withoutBrief: courses.filter((course) => course.brief_id === null).length,
    formats: [...new Set(courses.map((course) => course.package_format))].sort(),
  }));

  // Lineage, then version — the same `localeCompare` the rest of the console uses, with the
  // same known flaw (2.0.10 sorts before 2.0.9). Unknown last: it is not a version.
  return groups.sort((a, b) => {
    if (!a.version) return 1;
    if (!b.version) return -1;
    return (
      a.version.name.localeCompare(b.version.name) ||
      a.version.version.localeCompare(b.version.version)
    );
  });
}

function sharedCommissions(a: VersionGroup, b: VersionGroup): number {
  let shared = 0;
  for (const briefId of a.briefIds) if (b.briefIds.has(briefId)) shared += 1;
  return shared;
}
