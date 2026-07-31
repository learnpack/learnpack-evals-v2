import { IS_LOCAL_AUTH, SignInScreen } from "@/lib/auth";

export default function SignInPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-muted/30 p-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">LearnPack Evals</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pedagogical quality evaluation ·{" "}
          {IS_LOCAL_AUTH ? "local development mode" : "invite-only access"}
        </p>
      </div>
      <SignInScreen />
    </main>
  );
}
