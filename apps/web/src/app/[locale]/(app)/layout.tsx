import { setRequestLocale } from "next-intl/server";
import { AppNavbar } from "@/components/layout/AppNavbar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { UpsellBanner } from "@/components/usage/UpsellBanner";
import { isPlatformAdmin } from "@/lib/auth/platform";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { DEFAULT_UPSELL_THRESHOLD_PCT } from "@/lib/plans";
import { createClient } from "@/lib/supabase/server";
import { usageLevel, usagePercent } from "@/lib/usage";

export default async function AppLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  // Guard + единый доверенный tenant_id; редирект на login при отсутствии сессии/тенанта.
  const { userId, email, tenantId } = await getUserAndTenant(locale);
  const supabase = await createClient();
  const tenant = await supabase
    .from("tenants")
    .select("name, ai_budget_usd_month, upsell_threshold_pct")
    .eq("id", tenantId)
    .maybeSingle();
  const tenantName = tenant.data?.name ?? "";
  const budget = Number(tenant.data?.ai_budget_usd_month ?? 0);
  const threshold = tenant.data?.upsell_threshold_pct ?? DEFAULT_UPSELL_THRESHOLD_PCT;

  // numeric приходит из supabase-js строкой — Number() как и для остальных DB-чисел выше.
  const spendResult = await supabase.rpc("tenant_month_spend");
  const spend = Number(spendResult.data ?? 0);
  // Если строка тенанта не загрузилась (budget неизвестен) — не показываем плашку, чтобы
  // budget=0 из missing-data не выдал ложный blocked.
  const level = tenant.data != null ? usageLevel(spend, budget, threshold) : "ok";
  const percent = usagePercent(spend, budget);

  const admin = await isPlatformAdmin(userId);

  return (
    <ToastProvider>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <AppNavbar email={email} tenantName={tenantName} />
        {level !== "ok" ? (
          <div className="mx-auto w-full max-w-7xl px-4 pt-4 sm:px-6">
            <UpsellBanner level={level} percent={percent} locale={locale} suppressOnUsage />
          </div>
        ) : null}
        <div className="mx-auto flex w-full max-w-7xl">
          <aside className="hidden w-60 shrink-0 border-gray-200 md:block">
            <AppSidebar isPlatformAdmin={admin} />
          </aside>
          <main className="min-w-0 flex-1 px-4 py-6 sm:px-6">{children}</main>
        </div>
      </div>
    </ToastProvider>
  );
}
