import { NextRequest, NextResponse } from "next/server";
import { defaultLocale, locales } from "@/i18n/config";
export function middleware(request:NextRequest){const {pathname}=request.nextUrl;if(pathname.startsWith("/_next")||pathname.includes("."))return NextResponse.next();const hasLocale=locales.some(locale=>pathname===`/${locale}`||pathname.startsWith(`/${locale}/`));if(hasLocale)return NextResponse.next();const url=request.nextUrl.clone();url.pathname=`/${defaultLocale}${pathname}`;return NextResponse.redirect(url);}
export const config={matcher:["/((?!api|_next/static|_next/image|favicon.ico).*)"]};
