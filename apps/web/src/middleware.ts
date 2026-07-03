import createIntlMiddleware from "next-intl/middleware";
import { type NextRequest, NextResponse } from "next/server";
import { routing } from "./i18n/routing";
import { updateSession } from "./lib/supabase/middleware";

const intlMiddleware = createIntlMiddleware(routing);

const PROTECTED_SEGMENTS = ["dashboard"];

function localeOf(pathname: string): string {
  const first = pathname.split("/").filter(Boolean)[0];
  return routing.locales.includes(first as (typeof routing.locales)[number])
    ? first
    : routing.defaultLocale;
}

function isProtected(pathname: string): boolean {
  const segments = pathname.split("/").filter(Boolean);
  const afterLocale = routing.locales.includes(segments[0] as (typeof routing.locales)[number])
    ? segments.slice(1)
    : segments;
  return PROTECTED_SEGMENTS.includes(afterLocale[0] ?? "");
}

export default async function middleware(request: NextRequest) {
  const response = intlMiddleware(request);
  const user = await updateSession(request, response);

  if (isProtected(request.nextUrl.pathname) && user == null) {
    const locale = localeOf(request.nextUrl.pathname);
    return NextResponse.redirect(new URL(`/${locale}/login`, request.url));
  }
  return response;
}

export const config = {
  // все пути кроме api, _next, статики
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
