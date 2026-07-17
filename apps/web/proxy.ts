import { NextRequest, NextResponse } from "next/server";

/**
 * Lightweight, presence-only gate: redirects to /login if the session
 * cookie is entirely absent, before the page even renders. This is a UX
 * optimization only (avoids a flash of protected content) - it cannot and
 * does not validate the session (that requires a real call to the API,
 * which every protected page already makes via `useSession()`); the
 * actual authorization decision is always made server-side by the API.
 */
const PROTECTED_PATHS = ["/dashboard", "/team", "/usage", "/audit", "/onboarding"];
const SESSION_COOKIE_NAME = "gridkeep_session";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PATHS.some((path) => pathname.startsWith(path));

  if (isProtected && !request.cookies.get(SESSION_COOKIE_NAME)) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/team/:path*", "/usage/:path*", "/audit/:path*", "/onboarding"],
};
