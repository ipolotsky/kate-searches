import { getTranslations, setRequestLocale } from "next-intl/server";
import Link from "next/link";
import { AppNavbar } from "@/components/layout/AppNavbar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { UpsellBanner } from "@/components/usage/UpsellBanner";
import { isPlatformAdmin } from "@/lib/auth/platform";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { DEFAULT_UPSELL_THRESHOLD_PCT } from "@/lib/plans";
import { isStripeTestMode } from "@/lib/stripe/config";
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
    .select("name, ai_budget_usd_month, upsell_threshold_pct, subscription_status")
    .eq("id", tenantId)
    .maybeSingle();
  const tenantName = tenant.data?.name ?? "";
  const budget = Number(tenant.data?.ai_budget_usd_month ?? 0);
  const threshold = tenant.data?.upsell_threshold_pct ?? DEFAULT_UPSELL_THRESHOLD_PCT;
  const subscriptionStatus = tenant.data?.subscription_status ?? null;

  // numeric приходит из supabase-js строкой — Number() как и для остальных DB-чисел выше.
  const spendResult = await supabase.rpc("tenant_month_spend");
  const spend = Number(spendResult.data ?? 0);
  // Если строка тенанта не загрузилась (budget неизвестен) — не показываем плашку, чтобы
  // budget=0 из missing-data не выдал ложный blocked.
  const level = tenant.data != null ? usageLevel(spend, budget, threshold) : "ok";
  const percent = usagePercent(spend, budget);
  // Новый тенант (бюджет 0, подписки нет) — не «исчерпан», а «ещё не начал»: зовём в триал.
  const needsTrial = level === "blocked" && subscriptionStatus == null;

  const admin = await isPlatformAdmin(userId);
  const testMode = isStripeTestMode();
  const tBilling = await getTranslations("billing");

  return (
    <ToastProvider>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        {testMode ? (
          <div className="bg-amber-500 px-4 py-1.5 text-center text-xs font-medium text-amber-950">
            {tBilling("testMode")}
          </div>
        ) : null}
        <AppNavbar email={email} tenantName={tenantName} />
        <div className="flex w-full">
          <aside className="hidden w-60 shrink-0 md:block">
            <AppSidebar isPlatformAdmin={admin} />
          </aside>
          <main className="min-w-0 flex-1 px-6 py-8 lg:px-8">
            {needsTrial ? (
              <Link
                href={`/${locale}/billing`}
                className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-100"
              >
                <span>{tBilling("needTrial")}</span>
                <span className="font-semibold">{tBilling("startTrial")}</span>
              </Link>
            ) : level !== "ok" ? (
              <div className="mb-6">
                <UpsellBanner level={level} percent={percent} locale={locale} suppressOnUsage />
              </div>
            ) : null}
            {children}
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
