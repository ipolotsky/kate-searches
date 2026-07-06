import { redirect } from "next/navigation";
import { routing } from "@/i18n/routing";
import { createClient } from "@/lib/supabase/server";

export interface UserAndTenant {
  userId: string;
  email: string;
  tenantId: string;
}

const resolveLocale = (candidate: string): string =>
  routing.locales.includes(candidate as (typeof routing.locales)[number])
    ? candidate
    : routing.defaultLocale;

// Единственный доверенный источник tenant_id: резолв на сервере из auth.uid() -> users.
// Все server actions и RSC-страницы под (app) обязаны звать его, а не доверять клиентскому вводу.
export const getUserAndTenant = async (locale: string): Promise<UserAndTenant> => {
  const safeLocale = resolveLocale(locale);
  const supabase = await createClient();
  const userResult = await supabase.auth.getUser();
  const user = userResult.data.user;
  if (user == null) {
    redirect(`/${safeLocale}/login`);
  }

  const profile = await supabase.from("users").select("tenant_id").eq("id", user.id).maybeSingle();
  if (profile.data?.tenant_id == null) {
    redirect(`/${safeLocale}/login`);
  }

  return { userId: user.id, email: user.email ?? "", tenantId: profile.data.tenant_id };
};
