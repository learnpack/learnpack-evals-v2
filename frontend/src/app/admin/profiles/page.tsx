"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Quote } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { useProfiles, useProfilingCapabilities } from "@/lib/api/hooks";
import type { ProfileEntryResponse, ProfileResponse } from "@/lib/api/types";

export default function ProfilesPage() {
  const { data: profiles, isLoading, error } = useProfiles();
  const { data: capabilities } = useProfilingCapabilities();

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Content profiles</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Canonical evidence extracted from each course package, with verbatim citations.
          The engine never infers: an absent entry is a first-class finding. Profiling runs
          from the CLI (<code>app.cli profile-content</code>) or automatically once an
          adapter version is accepted.
        </p>
      </div>

      {capabilities && capabilities.length > 0 ? (
        <div className="mb-6 flex flex-wrap gap-2">
          {capabilities.map((c) => (
            <Badge key={c.package_format} variant={c.accepted ? "default" : "secondary"}>
              {c.package_format} · adapter v{c.adapter_version} ·{" "}
              {c.accepted ? "extraction accepted" : "not accepted yet"}
            </Badge>
          ))}
        </div>
      ) : null}

      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : !profiles || profiles.length === 0 ? (
        <EmptyState
          title="No profiles yet"
          hint="Profile a course with app.cli profile-content --content-id <id>."
        />
      ) : (
        <div className="space-y-4">
          {profiles.map((profile) => (
            <ProfileCard key={profile.profile_id} profile={profile} />
          ))}
        </div>
      )}
    </div>
  );
}

const PROVENANCE_LABEL = {
  declared_structured: "declared (structured)",
  declared_in_content: "declared in content",
  absent: "absent",
} as const;

function ProfileCard({ profile }: { profile: ProfileResponse }) {
  const [open, setOpen] = useState(false);
  const absentCount = profile.entries.filter((e) => e.provenance === "absent").length;

  return (
    <Card>
      <CardHeader>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex w-full items-center justify-between gap-3 text-left"
        >
          <div className="flex items-center gap-2">
            {open ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <CardTitle>{profile.external_id ?? profile.content_id}</CardTitle>
            <span className="text-sm text-muted-foreground">
              v{profile.content_version ?? "?"} · adapter {profile.package_format}/
              {profile.adapter_version}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {profile.status === "ok" ? (
              <Badge variant="secondary">
                {profile.entries.length} entries · {absentCount} absent
              </Badge>
            ) : null}
            <Badge variant={profile.status === "ok" ? "default" : "destructive"}>
              {profile.status}
            </Badge>
          </div>
        </button>
      </CardHeader>
      {open ? (
        <CardContent className="space-y-3">
          {profile.status === "failed" ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
              Extraction failed: {profile.error}
            </p>
          ) : (
            <>
              {profile.entries.map((entry) => (
                <ProfileEntry key={entry.data_requirement_id} entry={entry} />
              ))}
              {profile.extras.length > 0 ? (
                <div className="rounded-md border border-dashed p-3">
                  <p className="text-xs font-medium uppercase text-muted-foreground">
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
            </>
          )}
        </CardContent>
      ) : null}
    </Card>
  );
}

/** A readable "where this came from" line for the locator shapes the adapters emit. */
function describeLocator(locator: Record<string, unknown> | null): string {
  if (!locator) return "unknown source";
  const { source, key, kind, kinds, locator: path, path: jsonPath } = locator as {
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
          The content does not declare this — a finding, not a gap in extraction.
        </p>
      ) : (
        <>
          <pre className="mt-2 overflow-x-auto rounded bg-muted/40 p-2 text-xs">
            {JSON.stringify(entry.value, null, 2)}
          </pre>
          <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
            <Quote className="h-3 w-3 shrink-0" />
            <span>extracted from: {describeLocator(entry.locator)}</span>
            {entry.quote ? (
              <button
                type="button"
                onClick={() => setShowQuote(!showQuote)}
                className="text-primary hover:underline"
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
