"use client";

/** Clerk adapter — the real identity provider (ADR-0004). Default mode. */

import { ClerkProvider, SignIn, SignUp, UserButton, useAuth } from "@clerk/nextjs";
import { dark } from "@clerk/themes";
import { useTheme } from "next-themes";
import { useCallback } from "react";

// If a named Clerk JWT template carries the email/name claims, set this; otherwise the
// (customized) default session token is used. See .env.development.local.example.
const JWT_TEMPLATE = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE;

export function AuthProvider({ children }: { children: React.ReactNode }) {
  return <ClerkProvider>{children}</ClerkProvider>;
}

export function useAuthHeaders() {
  const { getToken } = useAuth();
  return useCallback(async (): Promise<Record<string, string>> => {
    const token = await getToken(JWT_TEMPLATE ? { template: JWT_TEMPLATE } : undefined);
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [getToken]);
}

/**
 * Clerk paints its own widgets, so it has to be told the theme separately.
 *
 * **On the widgets and not on `ClerkProvider`.** The provider wraps `<html>` — Clerk wants to be
 * the outermost thing there is — and the theme lives inside the body, so the provider cannot
 * read it. The three components below can, and they are the only Clerk surfaces this app
 * renders. It also keeps ADR-0008 intact: this file stays the only one importing Clerk.
 *
 * `resolvedTheme` rather than the chosen one, because `system` is not a look — it is a
 * question about the device, and Clerk has no opinion on it.
 */
function useClerkAppearance() {
  const { resolvedTheme } = useTheme();
  return resolvedTheme === "dark" ? { baseTheme: dark } : undefined;
}

export function UserMenu() {
  const appearance = useClerkAppearance();
  return <UserButton afterSignOutUrl="/sign-in" appearance={appearance} />;
}

export function SignInScreen() {
  const appearance = useClerkAppearance();
  return <SignIn appearance={appearance} />;
}

/**
 * Where an invitation link lands, and it must be `<SignUp/>`.
 *
 * An invited person does not exist yet: Clerk hands the ticket over with
 * `__clerk_status=sign_up`, and `<SignIn/>` cannot complete it — it renders and spins for
 * ever. This is the page `redirect_url` points at when the backend creates the Clerk
 * invitation (ADR-0049 §8).
 */
export function AcceptInvitationScreen() {
  const appearance = useClerkAppearance();
  return <SignUp fallbackRedirectUrl="/" appearance={appearance} />;
}
