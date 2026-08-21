"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState, LoadingState, Spinner } from "@/components/ui/states";
import { InviteForm } from "@/components/admin/invite-form";
import { ApiError } from "@/lib/api/client";
import {
  useAssessorPackages,
  useAssessors,
  useChangeAssessorRole,
  useInvitations,
  useMe,
  useRatifyAssessor,
  useResendInvitation,
  useRevokeInvitation,
  useSetAssessorActive,
  useSetAssessorExpertise,
} from "@/lib/api/hooks";
import type {
  AssessorPackageResponse,
  AssessorResponse,
  InvitationResponse,
  LineageVersion,
  RatificationDelta,
} from "@/lib/api/types";

/**
 * Who can judge — the two kinds of assessor, which are structurally different and not two
 * rows of one list (ADR-0016): a human is invited, arrives with a credential and is assigned
 * work; an automated assessor is a versioned artifact declared in code, and it judges
 * nothing until a person ratifies it against a published instrument version (ADR-0019).
 *
 * Each kind has exactly one act, and each list is ordered by it. Automated: ratify the
 * packages that are waiting — which is why those rows come from the package registry rather
 * than from the assessors table, so a package nobody ever ratified has no row at all and is
 * precisely the one somebody has to do something about. Human: invite (ADR-0049), which
 * creates no account — the assessor appears at that address's first sign-in, carrying the
 * role and the expertise the invitation declared.
 *
 * Automated stays the default view because ratification is the more frequent act; inviting
 * happens a handful of times per project.
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
          <code>app.cli ratify-assessor</code>. A human evaluator is{" "}
          <span className="font-medium text-foreground">invited</span>, and becomes an
          assessor at their first sign-in.
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

/**
 * The roster, in two tables that are one story: who is here, and who we are waiting for.
 *
 * The pending list comes first on purpose. It is the only part of this page with an act on
 * it, and an invitation that has been sitting there for a week is the thing somebody has to
 * do something about — the registered assessors are read, not acted on.
 */
function HumansSection({ assessors }: { assessors: AssessorResponse[] }) {
  const humans = assessors.filter((a) => a.kind === "human");
  const [inviting, setInviting] = useState(false);
  const invitations = useInvitations();
  // Which row is the reader's own: the one row whose role they may not touch (ADR-0050).
  const me = useMe();
  const pending = (invitations.data ?? []).filter((i) => i.status === "pending");

  return (
    <section className="space-y-8">
      <div>
        <div className="mb-3 flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold tracking-tight">Waiting to sign in</h2>
          <Button size="sm" onClick={() => setInviting(true)}>
            Invite evaluator
          </Button>
        </div>
        {invitations.isLoading ? (
          <LoadingState />
        ) : invitations.error ? (
          <ErrorState message={(invitations.error as Error).message} />
        ) : pending.length === 0 ? (
          <EmptyState
            title="Nobody is pending"
            hint="Inviting somebody records the role and the expertise they arrive with; the assessor appears at their first sign-in."
          />
        ) : (
          <Card>
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Invited</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pending.map((invitation) => (
                    <PendingRow key={invitation.invitation_id} invitation={invitation} />
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold tracking-tight">Registered</h2>
        {humans.length === 0 ? (
          <EmptyState
            title="No human assessors yet"
            hint="They become one the first time they sign in, carrying whatever the invitation declared."
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
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {humans.map((assessor) => (
                    <RegisteredRow
                      key={assessor.assessor_id}
                      assessor={assessor}
                      isSelf={assessor.assessor_id === me.data?.assessor_id}
                    />
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
        <p className="mt-3 text-sm text-muted-foreground">
          A role is granted by somebody else, never by the person holding it, and the last
          admin cannot be demoted — both would lock a door with no handle on this side. What
          a login can never do is change the role of an assessor that already exists.
        </p>
      </div>

      <Dialog
        open={inviting}
        onClose={() => setInviting(false)}
        title="Invite an evaluator"
        description="This registers the act, not an account: the assessor appears at their first sign-in, already carrying the role and expertise below."
      >
        <InviteForm onDone={() => setInviting(false)} />
      </Dialog>
    </section>
  );
}

/**
 * One registered human. The role cell is the act (ADR-0050) — a select, not a badge, except
 * on your own row, where it stays a badge with its reason beside it: a disabled control that
 * says why reads as a rule, a missing one reads as a bug.
 */
function RegisteredRow({
  assessor,
  isSelf,
}: {
  assessor: AssessorResponse;
  isSelf: boolean;
}) {
  const [pending, setPending] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const change = useChangeAssessorRole();
  const setActive = useSetAssessorActive();
  const setExpertise = useSetAssessorExpertise();
  const active = assessor.status === "active";
  const who = assessor.display_name ?? assessor.email ?? "They";

  function saveExpertise() {
    setExpertise.mutate(
      // Blank clears it: the backend treats an empty box and an unfilled one as the same.
      { assessorId: assessor.assessor_id, expertise: draft.trim() || null },
      {
        onSuccess: (updated) => {
          setEditing(false);
          toast.success(updated.expertise ? "Expertise updated." : "Expertise cleared.");
        },
        onError: (err) =>
          toast.error("Could not save that.", { description: (err as ApiError).message }),
      },
    );
  }

  function setActiveTo(next: boolean) {
    setActive.mutate(
      { assessorId: assessor.assessor_id, active: next },
      {
        onSuccess: () => {
          setLeaving(false);
          toast.success(next ? `${who} is back.` : `${who} has been deactivated.`);
        },
        onError: (err) => {
          setLeaving(false);
          toast.error("Could not change that.", { description: (err as ApiError).message });
        },
      },
    );
  }

  function confirm() {
    if (!pending) return;
    change.mutate(
      { assessorId: assessor.assessor_id, role: pending },
      {
        onSuccess: (updated) => {
          setPending(null);
          toast.success(
            `${updated.display_name ?? updated.email ?? "They"} ${
              updated.role === "admin" ? "can now administer" : "is now an evaluator"
            }.`,
          );
        },
        onError: (err) => {
          setPending(null);
          // A 409 states a rule — the last admin, your own row. Repeating the request
          // would only produce the same sentence.
          toast.error("Could not change the role.", {
            description: (err as ApiError).message,
          });
        },
      },
    );
  }

  return (
    <>
      <TableRow className={active ? undefined : "opacity-60"}>
        <TableCell className="font-medium">
          {assessor.display_name ?? "—"}
          {active ? null : (
            <Badge variant="outline" className="ml-2">
              deactivated
            </Badge>
          )}
          {/* Under the name, where a pending invitation shows it too: the profile is read
              to decide who gets which course, so it belongs next to the person — and so
              does the control that corrects it. Unlike the role, this is editable on your
              own row: saying what you work on grants you nothing. */}
          <button
            type="button"
            onClick={() => {
              setDraft(assessor.expertise ?? "");
              setEditing(true);
            }}
            className="mt-0.5 block max-w-xs break-words text-left text-xs font-normal text-muted-foreground underline decoration-dotted underline-offset-2 hover:text-foreground"
          >
            {assessor.expertise ?? "Add expertise"}
          </button>
        </TableCell>
        <TableCell className="text-sm text-muted-foreground">
          {assessor.email ?? "—"}
        </TableCell>
        <TableCell>
          {isSelf || !active ? (
            <span className="flex items-center gap-2">
              <Badge variant={assessor.role === "admin" ? "default" : "secondary"}>
                {assessor.role}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {isSelf ? "yours — somebody else grants it" : "they left"}
              </span>
            </span>
          ) : (
            <Select
              aria-label={`Role of ${who}`}
              className="h-9 w-40"
              value={assessor.role}
              disabled={change.isPending}
              onChange={(e) => setPending(e.target.value)}
            >
              <option value="evaluator">Evaluator</option>
              <option value="admin">Admin</option>
            </Select>
          )}
        </TableCell>
        <TableCell className="text-right">
          {isSelf ? null : active ? (
            <Button
              size="sm"
              variant="outline"
              disabled={setActive.isPending}
              onClick={() => setLeaving(true)}
            >
              Deactivate
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              disabled={setActive.isPending}
              onClick={() => setActiveTo(true)}
            >
              Reactivate
            </Button>
          )}
        </TableCell>
      </TableRow>

      <Dialog
        open={pending !== null}
        onClose={() => setPending(null)}
        title={pending === "admin" ? "Make them an admin?" : "Make them an evaluator?"}
      >
        <p className="text-sm text-muted-foreground">
          {pending === "admin" ? (
            <>
              <span className="font-medium text-foreground">
                {assessor.display_name ?? assessor.email}
              </span>{" "}
              will be able to register courses, run studies, invite people and grant this
              same role to others.
            </>
          ) : (
            <>
              <span className="font-medium text-foreground">
                {assessor.display_name ?? assessor.email}
              </span>{" "}
              will keep every evaluation they have already submitted, and lose access to the
              admin console.
            </>
          )}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          It is recorded with your name against it, and it can be changed back by anyone but
          them.
        </p>
        <div className="mt-4 flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => setPending(null)} disabled={change.isPending}>
            Cancel
          </Button>
          <Button onClick={confirm} disabled={change.isPending}>
            {change.isPending ? <Spinner /> : null}
            {pending === "admin" ? "Grant admin" : "Make evaluator"}
          </Button>
        </div>
      </Dialog>

      <Dialog
        open={editing}
        onClose={() => setEditing(false)}
        title={`Expertise of ${who}`}
        description="What this SME brings, as the roster knows it. It is read when deciding who should evaluate which course."
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveExpertise();
          }}
          className="space-y-4"
        >
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Instructional design · Python · K-12 maths"
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            Leave it empty to clear it. Recorded with your name against it.
          </p>
          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={() => setEditing(false)}
              disabled={setExpertise.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={setExpertise.isPending}>
              {setExpertise.isPending ? <Spinner /> : null} Save
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={leaving} onClose={() => setLeaving(false)} title={`Deactivate ${who}?`}>
        <p className="text-sm text-muted-foreground">
          They stop being offered work and can no longer sign in. Nothing is deleted:{" "}
          <span className="font-medium text-foreground">
            every evaluation they submitted stays exactly as it is
          </span>
          , and the reports that name them keep naming them — those record what happened.
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Reversible from this same row, and recorded with your name against it.
        </p>
        <div className="mt-4 flex justify-end gap-2 pt-2">
          <Button
            variant="outline"
            onClick={() => setLeaving(false)}
            disabled={setActive.isPending}
          >
            Cancel
          </Button>
          <Button onClick={() => setActiveTo(false)} disabled={setActive.isPending}>
            {setActive.isPending ? <Spinner /> : null} Deactivate
          </Button>
        </div>
      </Dialog>
    </>
  );
}

function PendingRow({ invitation }: { invitation: InvitationResponse }) {
  const resend = useResendInvitation();
  const revoke = useRevokeInvitation();
  const busy = resend.isPending || revoke.isPending;

  function act(
    mutation: typeof resend,
    id: string,
    done: string,
    failed: string,
  ) {
    mutation.mutate(id, {
      onSuccess: () => toast.success(done),
      onError: (err) => toast.error(failed, { description: (err as ApiError).message }),
    });
  }

  return (
    <TableRow>
      <TableCell className="font-medium">
        {invitation.email}
        {invitation.expertise ? (
          <span className="block text-xs font-normal text-muted-foreground">
            {invitation.expertise}
          </span>
        ) : null}
      </TableCell>
      <TableCell>
        <Badge variant={invitation.role === "admin" ? "default" : "secondary"}>
          {invitation.role}
        </Badge>
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {invitation.created_at ? new Date(invitation.created_at).toLocaleDateString() : "—"}
        {/* `expired` is derived from the window, not a state somebody wrote: a row can read
            `pending` and be past its date, and that is exactly what has to be visible. */}
        {invitation.expired ? (
          <Badge variant="warning" className="ml-2">
            expired
          </Badge>
        ) : null}
      </TableCell>
      <TableCell className="text-right">
        <span className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(
                resend,
                invitation.invitation_id,
                "The window is open again.",
                "Could not re-send.",
              )
            }
          >
            Re-send
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              act(
                revoke,
                invitation.invitation_id,
                "Invitation revoked; the address is free again.",
                "Could not revoke.",
              )
            }
          >
            Revoke
          </Button>
        </span>
      </TableCell>
    </TableRow>
  );
}
