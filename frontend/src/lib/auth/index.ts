/**
 * Auth seam: one interface, two implementations (ADR-0008).
 *
 * The mirror of the backend's `AUTH_MODE`. `clerk` is the real thing and the default; `local`
 * exists so contributors working on rubrics, metrics and evaluations can run the app with no
 * accounts and no cloud — identity is a header, chosen from a picker.
 *
 * Everything else in the app imports from here and never from `@clerk/nextjs`, so switching
 * modes touches no feature code.
 */

import { IS_LOCAL_AUTH } from "./mode";
import * as clerk from "./clerk";
import * as local from "./local";

export { AUTH_MODE, IS_LOCAL_AUTH, DEV_USER_COOKIE, DEV_USER_HEADER } from "./mode";

const impl = IS_LOCAL_AUTH ? local : clerk;

/** Wraps the app; in local mode it is a pass-through. */
export const AuthProvider = impl.AuthProvider;

/** Returns the headers that identify the caller to the API (Bearer token, or dev header). */
export const useAuthHeaders = impl.useAuthHeaders;

/** Header widget: Clerk's user button, or the local user switcher. */
export const UserMenu = impl.UserMenu;

/** The `/sign-in` body: Clerk's form, or the list of seeded local users. */
export const SignInScreen = impl.SignInScreen;
