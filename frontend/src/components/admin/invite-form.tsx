"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/states";
import { ApiError } from "@/lib/api/client";
import { useInviteAssessor } from "@/lib/api/hooks";

/**
 * Registering a human evaluator (ADR-0049). What this form creates is an **invitation**, not
 * an account: the assessor appears at that address's first login, already carrying the role
 * and the expertise typed here.
 *
 * The expertise field is the reason the form has four inputs instead of two. A human
 * assessor is "a concrete SME with an expertise profile" (GLOSSARY), and inviting is the
 * only moment somebody knows what that profile is — the person's own first login certainly
 * does not.
 */
export function InviteForm({ onDone }: { onDone: () => void }) {
  const invite = useInviteAssessor();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("evaluator");
  const [expertise, setExpertise] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) {
      toast.error("An address is what the invitation is redeemed against.");
      return;
    }
    invite.mutate(
      {
        email: email.trim(),
        role,
        display_name: displayName.trim() || null,
        expertise: expertise.trim() || null,
      },
      {
        onSuccess: (invitation) => {
          toast.success(`${invitation.email} is invited.`, {
            description: "They become an assessor the first time they sign in.",
          });
          onDone();
        },
        onError: (err) => {
          const error = err as ApiError;
          // A 409 states a fact and names its remedy — re-send, revoke, or change a role.
          // Repeating the request would only produce the same sentence.
          toast.error("Could not invite.", { description: error.message });
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="invite-email">Email</Label>
        <Input
          id="invite-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="ada@example.com"
          autoFocus
        />
        <p className="text-xs text-muted-foreground">
          The invitation is redeemed at this address&apos;s first sign-in, and only if the
          identity provider vouches for it.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="invite-name">Name</Label>
        <Input
          id="invite-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Ada Lovelace"
        />
        <p className="text-xs text-muted-foreground">
          Optional, and only a stand-in: the name the provider sends wins over this one.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="invite-role">Role</Label>
        <Select id="invite-role" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="evaluator">Evaluator</option>
          <option value="admin">Admin</option>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="invite-expertise">Expertise</Label>
        <Input
          id="invite-expertise"
          value={expertise}
          onChange={(e) => setExpertise(e.target.value)}
          placeholder="Instructional design · Python · K-12 maths"
        />
        <p className="text-xs text-muted-foreground">
          What this SME brings, as the roster knows it. Nothing else writes it.
        </p>
      </div>

      {/* Named, not hidden: until the provider adapter lands, inviting here and inviting in
          the provider are two acts, and finding that out at the door is worse. */}
      <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
        This does not invite them in Clerk. They still need an invitation there to be able to
        sign in at all.
      </p>

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="outline" onClick={onDone} disabled={invite.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={invite.isPending}>
          {invite.isPending ? <Spinner /> : null}
          Invite
        </Button>
      </div>
    </form>
  );
}
