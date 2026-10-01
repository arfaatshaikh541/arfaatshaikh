import { NextRequest, NextResponse } from "next/server";
import { defaultLocale, locales } from "@/i18n/config";

// Redirects paths without a locale to the default locale and tells the root layout which locale is being served
// (so <html lang dir> is correct for Arabic pages). Next.js strips the deployment basePath before this runs.
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (pathname.startsWith("/_next") || pathname.includes(".")) return NextResponse.next();
  const current = locales.find((locale) => pathname === `/${locale}` || pathname.startsWith(`/${locale}/`));
  if (current) {
    const headers = new Headers(request.headers);
    headers.set("x-woi-locale", current);
    return NextResponse.next({ request: { headers } });
  }
  const url = request.nextUrl.clone();
  url.pathname = `/${defaultLocale}${pathname}`;
  return NextResponse.redirect(url);
}

export const config = { matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"] };
