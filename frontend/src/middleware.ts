import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import {
  NextResponse,
  type NextFetchEvent,
  type NextMiddleware,
  type NextRequest,
} from "next/server";
import { DEV_USER_COOKIE, IS_LOCAL_AUTH } from "@/lib/auth/mode";

// Everything except the sign-in page (and Clerk's own callback routes) requires a session.
const isPublicRoute = createRouteMatcher(["/sign-in(.*)"]);

// Built lazily: calling clerkMiddleware() at module scope would run Clerk's setup in local
// mode, where there are no keys at all (ADR-0008).
let clerkHandler: NextMiddleware | null = null;

function protectWithClerk(request: NextRequest, event: NextFetchEvent) {
  clerkHandler ??= clerkMiddleware(async (auth, req) => {
    if (!isPublicRoute(req)) {
      await auth.protect();
    }
  });
  return clerkHandler(request, event);
}

/** Local mode: "signed in" means the identity cookie is set (see lib/auth/local.tsx). */
function protectLocally(request: NextRequest) {
  const signedIn = Boolean(request.cookies.get(DEV_USER_COOKIE)?.value);
  if (!signedIn && !request.nextUrl.pathname.startsWith("/sign-in")) {
    return NextResponse.redirect(new URL("/sign-in", request.url));
  }
  return NextResponse.next();
}

export default function middleware(request: NextRequest, event: NextFetchEvent) {
  return IS_LOCAL_AUTH ? protectLocally(request) : protectWithClerk(request, event);
}

export const config = {
  matcher: [
    // Skip Next internals and static files, run on everything else.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpg|jpeg|png|gif|svg|ico|webp|woff2?|ttf)).*)",
    "/(api|trpc)(.*)",
  ],
};
