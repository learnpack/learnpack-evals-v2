"use client";

import { useMemo, useState } from "react";
import { Quote } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useProfiles, useProfilingCapabilities } from "@/lib/api/hooks";
import type {
  ProfileCapabilitiesResponse,
  ProfileEntryResponse,
  ProfileResponse,
} from "@/lib/api/types";

/**
 * The designer's workbench: the screen someone reads to decide whether an extraction
 * adapter can be trusted — the judgement the `accept-extraction` act records.
 *
 * Two rules of the domain drive the visual weight here, and neither is decoration:
 *
 * 1. **Absence is a finding, not a failure.** A course that declares no objectives is
 *    telling us something true about its generator. So `absent` is never red; it is drawn
 *    as literal emptiness — an unfilled stretch of the provenance bar, a dashed entry card.
 * 2. **Only exceptions get colour.** A successful profile is the common case and carries no
 *    action, so it gets no badge: the provenance bar IS the evidence that it worked. The
 *    colour budget is spent on `failed`, which is the only row anyone has to do something
 *    about.
 */
export default function ProfilesPage() {
  const { data: profiles, isLoading, error } = useProfiles();
  const { data: capabilities } = useProfilingCapabilities();

  // Failures first — a broken extraction buried under twenty good ones is a failure the
  // page is hiding. Then by course, so the order is stable between visits.
  const ordered = useMemo(
    () =>
      [...(profiles ?? [])].sort((a, b) => {
        if (a.status !== b.status) return a.status === "failed" ? -1 : 1;
        return (a.external_id ?? a.content_id).localeCompare(b.external_id ?? b.content_id);
      }),
    [profiles],
  );
  const failed = ordered.filter((p) => p.status === "failed").length;

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Content profiles</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          What the extraction adapters read out of each course package, quoted verbatim.
          Nothing here is inferred: when a course does not declare something, the profile
          records it as <span className="font-medium text-foreground">absent</span> — a
          finding about the course, not a gap in the extraction.
        </p>
      </div>

      <ExtractionStatus capabilities={capabilities} />

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : ordered.length === 0 ? (
        <EmptyState
          title="No courses have been profiled yet"
          hint="Register a course — with the extraction accepted, profiling runs on its own. To profile one by hand, run app.cli profile-content --content-id <id>."
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            {ordered.length} {ordered.length === 1 ? "profile" : "profiles"}
            {failed > 0 ? (
              <>
                {" · "}
                <span className="font-medium text-destructive">
                  {failed} failed {failed === 1 ? "extraction" : "extractions"}, listed first
                </span>
              </>
            ) : (
              ", all extracted"
            )}
          </p>
          <div className="space-y-3">
            {ordered.map((profile) => (
              <ProfileCard key={profile.profile_id} profile={profile} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Whether each format's current adapter version is trusted. Inverted emphasis on purpose:
 * "accepted" is the resting state and stays quiet, while "not accepted" is the one that
 * changes what the system does — automatic profiling stays off — so it carries the colour
 * and says what to do about it.
 */
function ExtractionStatus({
  capabilities,
}: {
  capabilities: ProfileCapabilitiesResponse[] | undefined;
}) {
  if (!capabilities || capabilities.length === 0) return null;
  const pending = capabilities.filter((c) => !c.accepted);

  return (
    <div className="mb-6 rounded-lg border bg-muted/30 px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {capabilities.map((c) => (
          <span key={c.package_format} className="flex items-center gap-2 text-sm">
            <span className="font-medium">{c.package_format}</span>
            <span className="text-muted-foreground">adapter v{c.adapter_version}</span>
            {c.accepted ? (
              <span className="text-xs text-muted-foreground">extraction accepted</span>
            ) : (
              <Badge variant="warning">not accepted yet</Badge>
            )}
          </span>
        ))}
      </div>
      {pending.length > 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Registering a course does not profile it until someone accepts the adapter version
          that reads it. Review the profiles below, then run{" "}
          <code className="rounded bg-muted px-1 py-0.5">
            app.cli accept-extraction --package-format{" "}
            {pending.length === 1 ? pending[0].package_format : "<format>"} --email
            &lt;admin&gt;
          </code>
          .
        </p>
      ) : null}
    </div>
  );
}

const PROVENANCE_LABEL = {
  declared_structured: "declared (structured)",
  declared_in_content: "declared in content",
  absent: "absent",
} as const;

type Provenance = keyof typeof PROVENANCE_LABEL;

function countProvenances(entries: ProfileEntryResponse[]): Record<Provenance, number> {
  const counts: Record<Provenance, number> = {
    declared_structured: 0,
    declared_in_content: 0,
    absent: 0,
  };
  for (const entry of entries) counts[entry.provenance] += 1;
  return counts;
}

/**
 * The shape of one profile's evidence, at a glance: how much the course declared in a
 * structured field, how much it stated in prose, and how much it did not state at all.
 *
 * Comparing these bars down the page is the adapter-trust judgement this screen exists for —
 * a column of near-empty bars means the adapter is not finding what it should, or the
 * generator is not declaring it, and either is worth knowing before accepting the extraction.
 *
 * Two fills and a void: absent is the unfilled track, never a colour, because it is not an
 * error. Both fills are `primary`, which flips light-on-dark with the theme, so "more filled
 * = more evidence" survives dark mode without a second palette.
 */
function ProvenanceBar({ counts, total }: { counts: Record<Provenance, number>; total: number }) {
  if (total === 0) return null;
  const percent = (n: number) => `${(n / total) * 100}%`;

  // aria-hidden: the counts printed beside it say the same thing in words, and a screen
  // reader gains nothing from two renderings of one fact.
  return (
    <span aria-hidden className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-muted sm:flex">
      <span className="bg-primary" style={{ width: percent(counts.declared_structured) }} />
      <span className="bg-primary/45" style={{ width: percent(counts.declared_in_content) }} />
    </span>
  );
}

function ProfileCard({ profile }: { profile: ProfileResponse }) {
  const counts = countProvenances(profile.entries);
  const declared = counts.declared_structured + counts.declared_in_content;
  const failed = profile.status === "failed";

  return (
    <CollapsibleSection
      defaultOpen={false}
      title={profile.external_id ?? profile.content_id}
      badge={
        <>
          v{profile.content_version ?? "?"} · {profile.package_format}/{profile.adapter_version}
        </>
      }
      meta={
        failed ? (
          <Badge variant="destructive">failed</Badge>
        ) : (
          <>
            <ProvenanceBar counts={counts} total={profile.entries.length} />
            <span className="text-xs tabular-nums text-muted-foreground">
              {declared} of {profile.entries.length} declared
            </span>
          </>
        )
      }
    >
      {failed ? (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <p className="font-medium">The adapter could not read this package</p>
          <p className="mt-1 text-muted-foreground">{profile.error}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Fix the package or the adapter, then re-run{" "}
            <code className="rounded bg-muted px-1 py-0.5">
              app.cli profile-content --content-id {profile.content_id}
            </code>{" "}
            — a failed profile is replaced in place.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <ProvenanceLegend counts={counts} profiledAt={profile.profiled_at} />
          {profile.entries.map((entry) => (
            <ProfileEntry key={entry.data_requirement_id} entry={entry} />
          ))}
          {profile.extras.length > 0 ? (
            <div className="rounded-md border border-dashed p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Extras (out of contract)
              </p>
              <ul className="mt-2 space-y-1 text-sm">
                {profile.extras.map((extra) => (
                  <li key={extra.name}>
                    <span className="font-medium">{extra.name}</span>:{" "}
                    {JSON.stringify(extra.value)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </CollapsibleSection>
  );
}

/** The bar's key, spelled out once per open profile — and when the extraction ran. */
function ProvenanceLegend({
  counts,
  profiledAt,
}: {
  counts: Record<Provenance, number>;
  profiledAt: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b pb-3 text-xs text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-sm bg-primary" />
        {counts.declared_structured} {PROVENANCE_LABEL.declared_structured}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-sm bg-primary/45" />
        {counts.declared_in_content} {PROVENANCE_LABEL.declared_in_content}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-sm border border-dashed border-muted-foreground/60" />
        {counts.absent} absent
      </span>
      {profiledAt ? (
        <span className="ml-auto">extracted {new Date(profiledAt).toLocaleString()}</span>
      ) : null}
    </div>
  );
}

/** A readable "where this came from" line for the locator shapes the adapters emit. */
function describeLocator(locator: Record<string, unknown> | null): string {
  if (!locator) return "unknown source";
  const {
    source,
    key,
    kind,
    kinds,
    locator: path,
    path: jsonPath,
  } = locator as {
    source?: string;
    key?: string;
    kind?: string;
    kinds?: string[];
    locator?: string;
    path?: string;
  };
  if (source === "metadata" && key) return `declared metadata · ${key}`;
  if (source === "artifact" && kind) {
    return `artifact ${kind} · ${path ?? ""}${jsonPath ? ` · ${jsonPath}` : ""}`;
  }
  if (source === "artifacts" && kinds) return `artifacts · ${kinds.join(", ")}`;
  return JSON.stringify(locator);
}

function ProfileEntry({ entry }: { entry: ProfileEntryResponse }) {
  const absent = entry.provenance === "absent";
  const [showQuote, setShowQuote] = useState(false);
  return (
    <div className={`rounded-md border p-3 ${absent ? "border-dashed bg-muted/30" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{entry.data_requirement_id}</span>
        <Badge variant={absent ? "outline" : "secondary"}>
          {PROVENANCE_LABEL[entry.provenance]}
        </Badge>
      </div>
      {absent ? (
        <p className="mt-1 text-sm text-muted-foreground">
          The course does not declare this — a finding, not a gap in extraction.
        </p>
      ) : (
        <>
          <pre className="mt-2 overflow-x-auto rounded bg-muted/40 p-2 text-xs">
            {JSON.stringify(entry.value, null, 2)}
          </pre>
          <p className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <Quote className="h-3 w-3 shrink-0" />
            <span>extracted from: {describeLocator(entry.locator)}</span>
            {entry.quote ? (
              <button
                type="button"
                onClick={() => setShowQuote(!showQuote)}
                aria-expanded={showQuote}
                className="rounded text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {showQuote ? "hide verbatim quote" : "show verbatim quote"}
              </button>
            ) : null}
          </p>
          {showQuote && entry.quote ? (
            <p className="mt-1 rounded bg-muted/30 p-2 text-xs italic text-muted-foreground">
              {entry.quote}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
