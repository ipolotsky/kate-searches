import { type NextRequest, NextResponse } from "next/server";
import { routing } from "@/i18n/routing";
import { createClient } from "@/lib/supabase/server";

// Обмен кода на сессию (magic-link / OAuth). Для пароля с выключенным
// подтверждением почты не задействуется, но готов для этих сценариев.
export const GET = async (request: NextRequest): Promise<NextResponse> => {
  const code = request.nextUrl.searchParams.get("code");
  const first = request.nextUrl.pathname.split("/").filter(Boolean)[0];
  const locale = routing.locales.includes(first as (typeof routing.locales)[number])
    ? first
    : routing.defaultLocale;

  if (code != null) {
    const supabase = await createClient();
    await supabase.auth.exchangeCodeForSession(code);
  }
  return NextResponse.redirect(new URL(`/${locale}/dashboard`, request.url));
};
