/**
 * Which auth mode this build runs in (ADR-0008) — constants only, no React.
 *
 * `middleware.ts` runs on the edge runtime and must not pull the adapters (and therefore
 * React and Clerk) into its bundle, so the shared constants live in this leaf module.
 *
 * `NEXT_PUBLIC_AUTH_MODE` is inlined at build time: anything other than `local` is `clerk`,
 * so a missing or misspelled value fails safe.
 */

export const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE === "local" ? "local" : "clerk";

export const IS_LOCAL_AUTH = AUTH_MODE === "local";

/** Holds the chosen identity in local mode. Read by the middleware, written by the picker. */
export const DEV_USER_COOKIE = "evals_dev_user";

/** The request header the backend reads under AUTH_MODE=local (app/platform/auth_local.py). */
export const DEV_USER_HEADER = "X-Dev-User";
