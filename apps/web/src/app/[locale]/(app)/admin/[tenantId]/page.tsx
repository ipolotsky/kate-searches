import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { AdminTenantDetail } from "@/components/admin/AdminTenantDetail";
import type { StageSpend } from "@/components/usage/UsageSummary";
import { DEFAULT_UPSELL_THRESHOLD_PCT, PLAN_CATALOG, isPlan } from "@/lib/plans";
import { createAdminClient } from "@/lib/supabase/admin";
import { monthStartIso } from "@/lib/usage";

export default async function AdminTenantPage({
  params,
}: {
  params: Promise<{ locale: string; tenantId: string }>;
}) {
  const { locale, tenantId } = await params;
  setRequestLocale(locale);
  const admin = createAdminClient();

  const tenantResult = await admin
    .from("tenants")
    .select("id, name, plan, ai_budget_usd_month, upsell_threshold_pct")
    .eq("id", tenantId)
    .maybeSingle();
  if (tenantResult.error != null) {
    throw new Error(tenantResult.error.message);
  }
  const tenant = tenantResult.data;
  if (tenant == null) {
    notFound();
  }

  const stageResult = await admin.rpc("admin_tenant_usage_by_stage", {
    p_tenant_id: tenantId,
    p_since: monthStartIso(),
  });
  if (stageResult.error != null) {
    throw new Error(stageResult.error.message);
  }
  const stages: StageSpend[] = (stageResult.data ?? [])
    .map((x) => ({ stage: x.stage, cost: Number(x.cost_usd), calls: Number(x.calls) }))
    .sort((a, b) => b.cost - a.cost);
  const spend = stages.reduce((sum, x) => sum + x.cost, 0);

  const spec = isPlan(tenant.plan) ? PLAN_CATALOG[tenant.plan] : null;

  return (
    <AdminTenantDetail
      locale={locale}
      tenantId={tenant.id}
      name={tenant.name}
      plan={tenant.plan}
      budget={Number(tenant.ai_budget_usd_month)}
      threshold={tenant.upsell_threshold_pct ?? DEFAULT_UPSELL_THRESHOLD_PCT}
      spend={spend}
      stages={stages}
      price={spec?.price ?? null}
      sourcesLimit={spec?.sources ?? null}
      draftsLimit={spec?.drafts ?? null}
    />
  );
}
