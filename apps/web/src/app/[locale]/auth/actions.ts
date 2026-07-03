"use server";

import { redirect } from "next/navigation";
import { routing } from "@/i18n/routing";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

const resolveLocale = (candidate: string): string =>
  routing.locales.includes(candidate as (typeof routing.locales)[number])
    ? candidate
    : routing.defaultLocale;

export const login = async (formData: FormData): Promise<void> => {
  const locale = resolveLocale(String(formData.get("locale") ?? ""));
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  const supabase = await createClient();
  const result = await supabase.auth.signInWithPassword({ email, password });
  if (result.error != null) {
    redirect(`/${locale}/login?error=1`);
  }
  redirect(`/${locale}/dashboard`);
};

export const register = async (formData: FormData): Promise<void> => {
  const locale = resolveLocale(String(formData.get("locale") ?? ""));
  const company = String(formData.get("company") ?? "").trim();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  if (company.length === 0) {
    redirect(`/${locale}/register?error=1`);
  }

  const supabase = await createClient();
  const signUp = await supabase.auth.signUp({ email, password });
  if (signUp.error != null || signUp.data.user == null) {
    redirect(`/${locale}/register?error=1`);
  }
  // Существующий email при включённом подтверждении почты: Supabase возвращает
  // user с пустым identities и без ошибки. Не плодим мусорный тенант.
  if (signUp.data.user.identities != null && signUp.data.user.identities.length === 0) {
    redirect(`/${locale}/register?error=1`);
  }

  // Провижининг под service_role (обходит RLS). При сбое откатываем частичное состояние.
  const userId = signUp.data.user.id;
  const admin = createAdminClient();
  const tenant = await admin
    .from("tenants")
    .insert({ name: company, default_locale: locale })
    .select("id")
    .single();
  if (tenant.error != null) {
    await admin.auth.admin.deleteUser(userId);
    redirect(`/${locale}/register?error=1`);
  }
  const userRow = await admin.from("users").insert({
    id: userId,
    tenant_id: tenant.data.id,
    email,
    role: "owner",
    locale,
  });
  if (userRow.error != null) {
    await admin.from("tenants").delete().eq("id", tenant.data.id);
    await admin.auth.admin.deleteUser(userId);
    redirect(`/${locale}/register?error=1`);
  }
  redirect(`/${locale}/dashboard`);
};

export const signOut = async (formData: FormData): Promise<void> => {
  const locale = resolveLocale(String(formData.get("locale") ?? ""));
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect(`/${locale}/login`);
};
