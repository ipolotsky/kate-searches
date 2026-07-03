import { createServerClient } from "@supabase/ssr";
import type { NextRequest, NextResponse } from "next/server";
import type { User } from "@supabase/supabase-js";

// Обновляет сессию Supabase и переносит cookie на ответ next-intl. Возвращает юзера.
export const updateSession = async (
  request: NextRequest,
  response: NextResponse,
): Promise<User | null> => {
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach((x) => {
            request.cookies.set(x.name, x.value);
            response.cookies.set(x.name, x.value, x.options);
          });
        },
      },
    },
  );
  const result = await supabase.auth.getUser();
  return result.data.user;
};
