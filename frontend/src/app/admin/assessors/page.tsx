"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Dialog } from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import { useAssessorPackages, useAssessors, useRatifyAssessor } from "@/lib/api/hooks";
import type {
  AssessorPackageResponse,
  AssessorResponse,
  LineageVersion,
  RatificationDelta,
} from "@/lib/api/types";

/**
 * Who can judge — the two kinds of assessor, which are structurally different and not two
 * rows of one list (ADR-0016): a human arrives with a credential and is assigned work; an
 * automated assessor is a versioned artifact declared in code, and it judges nothing until
 * a person ratifies it against a published instrument version (ADR-0019).
 *
 * Automated is the default view because it is the one with an act on it. The humans are
 * here to be looked up, not acted on: the acts that concern them live in campaigns.
 *
 * The automated rows come from the package registry rather than from the assessors table,
 * and that is the point: a package that has never been ratified has no row at all, and it
 * is precisely the one somebody has to do something about.
 */

type Group = "automated" | "humans" | "both";

const GROUPS: { value: Group; label: string }[] = [
  { value: "automated", label: "Automated" },
  { value: "humans", label: "Humans" },
  { value: "both", label: "Both" },
];

export default function AssessorsPage() {
  const [group, setGroup] = useState<Group>("automated");
  const packages = useAssessorPackages();
  const humans = useAssessors();

  const showAutomated = group === "automated" || group === "both";
  const showHumans = group === "humans" || group === "both";
  const active = showAutomated ? packages : humans;

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Assessors</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Who produces evaluation results. An automated assessor is declared in code and
          becomes able to persist judgments only once it is{" "}
          <span className="font-medium text-foreground">ratified</span> against a published
          instrument version — a human act, taken here or with{" "}
          <code>app.cli ratify-assessor</code>.
        </p>
      </div>

      <div className="mb-6 inline-flex rounded-lg border p-1">
        {GROUPS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => setGroup(option.value)}
            className={
              group === option.value
                ? "rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
                : "rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent"
            }
          >
            {option.label}
          </button>
        ))}
      </div>

      {active.isLoading ? (
        <LoadingState />
      ) : active.error ? (
        <ErrorState message={(active.error as Error).message} />
      ) : (
        <div className="space-y-8">
          {showAutomated ? <AutomatedSection packages={packages.data ?? []} /> : null}
          {showHumans ? <HumansSection assessors={humans.data ?? []} /> : null}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------- automated

function AutomatedSection({ packages }: { packages: AssessorPackageResponse[] }) {
  if (packages.length === 0) {
    return (
      <EmptyState
        title="No automated assessors"
        hint="They are declared in code, in app/modules/evaluation/infrastructure/assessors."
      />
    );
  }
  return (
    <section className="space-y-4">
      {packages.map((pkg) => (
        <PackageCard key={`${pkg.name}:${pkg.version}`} pkg={pkg} />
      ))}
    </section>
  );
}

const STATUS_VARIANT = {
  draft: "secondary",
  published: "default",
  deprecated: "outline",
} as const;

function PackageCard({ pkg }: { pkg: AssessorPackageResponse }) {
  const [target, setTarget] = useState<LineageVersion | null>(null);
  const ratified = pkg.lineage_versions.filter((v) => v.ratified).length;
  const awaiting = pkg.lineage_versions.filter(
    (v) => !v.ratified && v.status === "published",
  ).length;

  return (
    <>
      {/* Collapsed by default: the list is read to find the package that needs something,
          not to study one. What the closed row has to answer is exactly that — hence
          `awaiting`, the count of published versions with a Ratify button waiting inside. */}
      <CollapsibleSection
        defaultOpen={false}
        title={pkg.display_name}
        badge={
          <>
            <code>
              {pkg.name}:{pkg.version}
            </code>{" "}
            · lineage <code>{pkg.instrument_id}</code>
          </>
        }
        meta={
          <span className="flex flex-wrap items-center gap-2">
            {pkg.uses_llm ? <Badge variant="warning">LLM</Badge> : null}
            <Badge variant="secondary">
              {pkg.executes.length} executed · {Object.keys(pkg.abstains).length} abstained
            </Badge>
            {awaiting > 0 ? (
              <Badge variant="warning">{awaiting} to ratify</Badge>
            ) : ratified > 0 ? (
              <Badge variant="success">ratifies {ratified}</Badge>
            ) : (
              <Badge variant="outline">never ratified</Badge>
            )}
          </span>
        }
      >
        {pkg.lineage_versions.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No version of this lineage exists yet. Import one with{" "}
            <code>app.cli import-instrument</code>; ratifying comes after publishing it.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Instrument version</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Ratified</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {pkg.lineage_versions.map((version) => (
                <TableRow key={version.instrument_version_id}>
                  <TableCell className="font-medium">
                    <code>{version.instrument_version_id}</code>
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[version.status]}>{version.status}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {version.ratified ? (
                      <>
                        by {version.ratified_by_name ?? "unknown"}
                        {version.ratified_at
                          ? ` · ${new Date(version.ratified_at).toLocaleDateString()}`
                          : ""}
                      </>
                    ) : version.status === "published" ? (
                      "not yet"
                    ) : (
                      // A draft is not "pending ratification": its remedy is publishing it.
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {!version.ratified && version.status === "published" ? (
                      <Button size="sm" onClick={() => setTarget(version)}>
                        Ratify
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CollapsibleSection>
      {/* Outside the disclosure: a dialog that unmounts when its section collapses would
          take an in-flight act with it. */}
      <RatifyDialog pkg={pkg} version={target} onClose={() => setTarget(null)} />
    </>
  );
}

// -------------------------------------------------------------------------- the act

function RatifyDialog({
  pkg,
  version,
  onClose,
}: {
  pkg: AssessorPackageResponse;
  version: LineageVersion | null;
  onClose: () => void;
}) {
  // Set only when the act comes back asking for a decision per criterion (409).
  const [pending, setPending] = useState<RatificationDelta[] | null>(null);
  const [confirmed, setConfirmed] = useState<string[]>([]);
  const ratify = useRatifyAssessor();

  function close() {
    setPending(null);
    setConfirmed([]);
    onClose();
  }

  function submit(ids: string[]) {
    if (!version) return;
    ratify.mutate(
      {
        name: pkg.name,
        version: pkg.version,
        instrument_version_id: version.instrument_version_id,
        confirmed: ids,
      },
      {
        onSuccess: (result) => {
          close();
          toast.success(
            result.newly_ratified
              ? `${pkg.name}:${pkg.version} can now evaluate with ${result.instrument_version_id}.`
              : "That version was already ratified.",
          );
        },
        onError: (err) => {
          const error = err as ApiError;
          const criteria = error.data?.criteria as RatificationDelta[] | undefined;
          if (error.status === 409 && criteria?.length) {
            // Not a failure to retry: the act is waiting for a decision it will not take.
            setPending(criteria);
            return;
          }
          close();
          toast.error("Could not ratify.", { description: error.message });
        },
      },
    );
  }

  if (!version) return null;

  return (
    <Dialog
      open
      onClose={close}
      title={
        pending
          ? "Confirm what changed"
          : `Ratify ${pkg.name}:${pkg.version} for ${version.instrument_version_id}?`
      }
    >
      {pending ? (
        <>
          <p className="text-sm text-muted-foreground">
            These criteria are new or reworded since the last version this assessor
            ratified. Confirming one states that its executor still realizes the text below
            — the code is not re-read, the decision is yours. If an executor no longer fits,
            cancel: changing it is a new assessor version, not a ratification.
          </p>
          <ul className="mt-4 space-y-3">
            {pending.map((criterion) => (
              <li key={criterion.criterion_id} className="rounded-md border p-3">
                <label className="flex gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 shrink-0"
                    checked={confirmed.includes(criterion.criterion_id)}
                    onChange={(e) =>
                      setConfirmed((current) =>
                        e.target.checked
                          ? [...current, criterion.criterion_id]
                          : current.filter((id) => id !== criterion.criterion_id),
                      )
                    }
                  />
                  <span>
                    <span className="font-medium">
                      <code>{criterion.criterion_id}</code>{" "}
                      <Badge variant="outline">{criterion.change}</Badge>
                    </span>
                    <span className="mt-1 block text-muted-foreground">
                      {criterion.pass_condition}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={close} disabled={ratify.isPending}>
              Cancel
            </Button>
            <Button
              onClick={() => submit(confirmed)}
              disabled={ratify.isPending || confirmed.length !== pending.length}
            >
              {ratify.isPending ? <Spinner /> : null} Confirm and ratify
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Ratifying makes this assessor able to <strong>persist</strong> judgments against{" "}
            <code>{version.instrument_version_id}</code>. Until now its results could only
            come from a dry run, which writes nothing; from here they become evidence a
            study can publish.
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            It records who decided and when, and it cannot be undone — there is no
            un-ratify. It does not change the assessor&apos;s identity and does not carry
            over to a future version of it: a new artifact ratifies on its own.
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            What the act checks is coverage, never quality. Whether this assessor judges
            well is what the calibration runs are for, and that reading is the team&apos;s.
          </p>
          <div className="mt-4 flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={close} disabled={ratify.isPending}>
              Cancel
            </Button>
            <Button onClick={() => submit([])} disabled={ratify.isPending}>
              {ratify.isPending ? <Spinner /> : null} Ratify
            </Button>
          </div>
        </>
      )}
    </Dialog>
  );
}

// ---------------------------------------------------------------------------- humans

function HumansSection({ assessors }: { assessors: AssessorResponse[] }) {
  const humans = assessors.filter((a) => a.kind === "human");

  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold tracking-tight">Humans</h2>
      {humans.length === 0 ? (
        <EmptyState
          title="No human assessors yet"
          hint="They appear the first time they sign in (invite-only)."
        />
      ) : (
        <Card>
          <CardContent className="pt-6">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {humans.map((assessor) => (
                  <TableRow key={assessor.assessor_id}>
                    <TableCell className="font-medium">
                      {assessor.display_name ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {assessor.email ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={assessor.role === "admin" ? "default" : "secondary"}>
                        {assessor.role}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      <p className="mt-3 text-sm text-muted-foreground">
        Roles are changed with <code>app.cli set-role</code>, never from a screen: a login
        must not be able to escalate a privilege.
      </p>
    </section>
  );
}
