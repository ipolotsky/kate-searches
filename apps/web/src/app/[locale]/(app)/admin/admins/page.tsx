import { setRequestLocale } from "next-intl/server";
import { type AdminRow, PlatformAdminsManager } from "@/components/admin/PlatformAdminsManager";
import { assertPlatformAdmin } from "@/lib/auth/platform";
import { createAdminClient } from "@/lib/supabase/admin";

const oneOf = <T,>(value: T | T[] | null): T | null =>
  Array.isArray(value) ? (value[0] ?? null) : value;

export default async function AdminAdminsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const identity = await assertPlatformAdmin(locale);

  // service_role: platform_admins RLS отдаёт только свою строку; список всех — через сервисную роль.
  const admin = createAdminClient();
  const result = await admin
    .from("platform_admins")
    .select("user_id, created_at, users(email)")
    .order("created_at", { ascending: true });
  if (result.error != null) {
    throw new Error(result.error.message);
  }
  const rows: AdminRow[] = (result.data ?? []).map((row) => ({
    userId: row.user_id,
    email: oneOf(row.users)?.email ?? "",
    createdAt: row.created_at,
  }));

  return <PlatformAdminsManager rows={rows} currentUserId={identity.userId} locale={locale} />;
}
