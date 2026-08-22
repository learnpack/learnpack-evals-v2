import { AcceptInvitationScreen, IS_LOCAL_AUTH } from "@/lib/auth";

/**
 * Where an invitation email lands (ADR-0049).
 *
 * A separate route from `/sign-in`, because the person arriving here **does not exist yet**:
 * Clerk hands the invitation over as a sign-up ticket, and the sign-in form cannot complete
 * one — it renders and spins for ever. A catch-all segment because Clerk's component owns
 * the sub-paths of its own multi-step flow.
 */
export default function AcceptInvitationPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-muted/30 p-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">LearnPack Evals</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {IS_LOCAL_AUTH
            ? "local development mode"
            : "You were invited — finish creating your account"}
        </p>
      </div>
      <AcceptInvitationScreen />
    </main>
  );
}
