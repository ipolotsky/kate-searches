import { getTranslations, setRequestLocale } from "next-intl/server";
import { AdminTenantsTable, type TenantReportRow } from "@/components/admin/AdminTenantsTable";
import { createAdminClient } from "@/lib/supabase/admin";
import { monthStartIso } from "@/lib/usage";

export default async function AdminPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("admin");

  // service_role: кросс-тенант отчёт (RLS не даёт authenticated видеть чужие тенанты).
  // admin_tenant_report — security definer, execute только service_role.
  const admin = createAdminClient();
  const report = await admin.rpc("admin_tenant_report", { p_since: monthStartIso() });
  if (report.error != null) {
    throw new Error(report.error.message);
  }
  const rows: TenantReportRow[] = report.data ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t("title")}</h1>
        <p className="text-sm text-gray-500">{t("subtitle")}</p>
      </div>
      <AdminTenantsTable rows={rows} locale={locale} />
    </div>
  );
}
