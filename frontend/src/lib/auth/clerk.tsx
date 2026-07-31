"use client";

/** Clerk adapter — the real identity provider (ADR-0004). Default mode. */

import { ClerkProvider, SignIn, UserButton, useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

// If a named Clerk JWT template carries the email/name claims, set this; otherwise the
// (customized) default session token is used. See .env.local.example.
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

export function UserMenu() {
  return <UserButton afterSignOutUrl="/sign-in" />;
}

export function SignInScreen() {
  return <SignIn />;
}
