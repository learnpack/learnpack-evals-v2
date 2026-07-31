"use client";

/**
 * Local adapter — no authentication at all (ADR-0008).
 *
 * Identity is a cookie holding an email, sent to the API as `X-Dev-User`. The backend only
 * honours it under `AUTH_MODE=local`, and refuses that mode in production, so this cannot
 * become a way in anywhere real.
 *
 * The users come from `GET /dev/identities` (seeded by `app.cli seed-demo`), so the picker
 * never drifts from the database.
 */

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { DevIdentity } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/ui/states";
import { DEV_USER_COOKIE, DEV_USER_HEADER } from "./mode";

const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

function readDevUser(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${DEV_USER_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Switching user reloads the page on purpose: a full navigation drops the TanStack Query
 * cache, so no data from the previous identity survives on screen.
 */
function signInAs(email: string) {
  document.cookie =
    `${DEV_USER_COOKIE}=${encodeURIComponent(email)}; path=/; ` +
    `max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
  window.location.assign("/");
}

function signOut() {
  document.cookie = `${DEV_USER_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
  window.location.assign("/sign-in");
}

function useIdentities() {
  return useQuery({
    queryKey: ["dev", "identities"],
    queryFn: () => apiFetch<DevIdentity[]>("/dev/identities", {}),
    staleTime: 60_000,
  });
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function useAuthHeaders() {
  // Read at call time, not at render: the cookie can change without a re-render.
  return useCallback(async (): Promise<Record<string, string>> => {
    const email = readDevUser();
    return email ? { [DEV_USER_HEADER]: email } : {};
  }, []);
}

/**
 * The cookie only exists in the browser, so it cannot be read while rendering: most pages are
 * prerendered, and reading it during render would make the server HTML ("Not signed in")
 * disagree with the client's and trigger a hydration mismatch.
 */
function useCurrentDevUser(): string | null {
  const [email, setEmail] = useState<string | null>(null);
  useEffect(() => setEmail(readDevUser()), []);
  return email;
}

export function UserMenu() {
  const [open, setOpen] = useState(false);
  const { data: identities } = useIdentities();
  const current = useCurrentDevUser();

  return (
    <div className="relative">
      <Button variant="outline" size="sm" onClick={() => setOpen((v) => !v)}>
        <span className="max-w-[16rem] truncate">{current ?? "Local user"}</span>
        <Badge variant="warning">local</Badge>
      </Button>

      {open ? (
        <div className="absolute right-0 z-20 mt-2 w-72 rounded-md border bg-background p-1 shadow-md">
          <p className="px-3 py-2 text-xs font-medium text-muted-foreground">Switch user</p>
          {(identities ?? []).map((identity) => (
            <button
              key={identity.email}
              onClick={() => signInAs(identity.email)}
              className="flex w-full items-center justify-between gap-2 rounded-sm px-3 py-2 text-left text-sm hover:bg-accent"
            >
              <span className="truncate">
                {identity.display_name ?? identity.email}
                <span className="block text-xs text-muted-foreground">{identity.email}</span>
              </span>
              <Badge variant={identity.role === "admin" ? "default" : "secondary"}>
                {identity.role}
              </Badge>
            </button>
          ))}
          <button
            onClick={signOut}
            className="mt-1 w-full rounded-sm border-t px-3 py-2 text-left text-sm hover:bg-accent"
          >
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function SignInScreen() {
  const { data: identities, isLoading, error } = useIdentities();

  if (isLoading) return <LoadingState label="Loading local users…" />;
  if (error) {
    return (
      <ErrorState
        message={`${(error as Error).message} — is the API running with AUTH_MODE=local?`}
      />
    );
  }
  if (!identities?.length) {
    return <ErrorState message="No users yet. Run: uv run python -m app.cli seed-demo" />;
  }

  return (
    <div className="w-full max-w-sm rounded-lg border bg-background p-2 shadow-sm">
      <p className="px-3 py-2 text-xs font-medium text-muted-foreground">
        Local mode — pick who to sign in as
      </p>
      {identities.map((identity) => (
        <button
          key={identity.email}
          onClick={() => signInAs(identity.email)}
          className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-3 text-left hover:bg-accent"
        >
          <span className="truncate">
            <span className="text-sm font-medium">{identity.display_name ?? identity.email}</span>
            <span className="block text-xs text-muted-foreground">{identity.email}</span>
          </span>
          <Badge variant={identity.role === "admin" ? "default" : "secondary"}>
            {identity.role}
          </Badge>
        </button>
      ))}
    </div>
  );
}
