import { getTranslations, setRequestLocale } from "next-intl/server";
import { UpsellBanner } from "@/components/usage/UpsellBanner";
import { type StageSpend, UsageSummary } from "@/components/usage/UsageSummary";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { DEFAULT_UPSELL_THRESHOLD_PCT, PLAN_CATALOG, isPlan } from "@/lib/plans";
import { createClient } from "@/lib/supabase/server";
import { monthStartIso, usageLevel, usagePercent } from "@/lib/usage";

export default async function UsagePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("usage");
  const { tenantId } = await getUserAndTenant(locale);
  const supabase = await createClient();

  const stageResult = await supabase.rpc("tenant_month_usage_by_stage");
  if (stageResult.error != null) {
    throw new Error(stageResult.error.message);
  }
  const stages: StageSpend[] = (stageResult.data ?? [])
    .map((row) => ({ stage: row.stage, cost: Number(row.cost_usd), calls: Number(row.calls) }))
    .sort((a, b) => b.cost - a.cost);
  const spend = stages.reduce((sum, x) => sum + x.cost, 0);

  const tenantResult = await supabase
    .from("tenants")
    .select("plan, ai_budget_usd_month, upsell_threshold_pct")
    .eq("id", tenantId)
    .maybeSingle();
  if (tenantResult.error != null) {
    throw new Error(tenantResult.error.message);
  }
  const plan = tenantResult.data?.plan ?? "pilot";
  const budget = Number(tenantResult.data?.ai_budget_usd_month ?? 0);
  const threshold = tenantResult.data?.upsell_threshold_pct ?? DEFAULT_UPSELL_THRESHOLD_PCT;

  const draftsResult = await supabase
    .from("posts")
    .select("id", { count: "exact", head: true })
    .gte("created_at", monthStartIso());
  if (draftsResult.error != null) {
    throw new Error(draftsResult.error.message);
  }

  const percent = usagePercent(spend, budget);
  const level = usageLevel(spend, budget, threshold);
  const spec = isPlan(plan) ? PLAN_CATALOG[plan] : null;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t("title")}</h1>
        <p className="text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      {level !== "ok" ? (
        <UpsellBanner level={level} percent={percent} locale={locale} showCta={false} />
      ) : null}

      <UsageSummary
        plan={plan}
        spend={spend}
        budget={budget}
        percent={percent}
        level={level}
        draftsThisMonth={draftsResult.count ?? 0}
        stages={stages}
        sourcesLimit={spec?.sources ?? null}
        draftsLimit={spec?.drafts ?? null}
      />
    </div>
  );
}
