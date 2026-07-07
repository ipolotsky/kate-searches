import { notFound } from "next/navigation";
import { type UserAndTenant, getUserAndTenant } from "@/lib/auth/tenant";
import { createClient } from "@/lib/supabase/server";

// Платформенный (кросс-тенант) админ — по таблице platform_admins. RLS self-select даёт юзеру
// его собственную строку, поэтому проверка идёт под обычным authenticated-клиентом (без service_role).
export const isPlatformAdmin = async (userId: string): Promise<boolean> => {
  const supabase = await createClient();
  const result = await supabase
    .from("platform_admins")
    .select("user_id")
    .eq("user_id", userId)
    .maybeSingle();
  return result.data != null;
};

// Гейт для admin-RSC и server actions: не-админа отдаём в 404 (не раскрываем существование раздела).
export const assertPlatformAdmin = async (locale: string): Promise<UserAndTenant> => {
  const identity = await getUserAndTenant(locale);
  if (!(await isPlatformAdmin(identity.userId))) {
    notFound();
  }
  return identity;
};
