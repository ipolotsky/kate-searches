import { getTranslations, setRequestLocale } from "next-intl/server";
import { BillingPanel } from "@/components/billing/BillingPanel";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { PLAN_CATALOG, TRIAL_DRAFTS_LIMIT } from "@/lib/plans";
import { createClient } from "@/lib/supabase/server";

const DAY_MS = 86_400_000;

export default async function BillingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const { tenantId } = await getUserAndTenant(locale);
  const supabase = await createClient();

  const tenant = await supabase
    .from("tenants")
    .select(
      "subscription_status, trial_ends_at, billing_enabled, stripe_customer_id, trial_drafts_limit",
    )
    .eq("id", tenantId)
    .maybeSingle();
  const draftsCount = await supabase.from("posts").select("id", { count: "exact", head: true });

  const t = await getTranslations("billing");

  const trialEndsAt = tenant.data?.trial_ends_at ?? null;
  const trialDaysLeft =
    trialEndsAt != null
      ? Math.max(0, Math.ceil((new Date(trialEndsAt).getTime() - Date.now()) / DAY_MS))
      : null;

  const plans = (["starter", "pro", "agency"] as const).map((plan) => ({
    plan,
    price: PLAN_CATALOG[plan].price,
    sources: PLAN_CATALOG[plan].sources,
    drafts: PLAN_CATALOG[plan].drafts,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t("title")}</h1>
        <p className="text-sm text-gray-500">{t("subtitle")}</p>
      </div>
      <BillingPanel
        locale={locale}
        plans={plans}
        status={tenant.data?.subscription_status ?? null}
        trialDaysLeft={trialDaysLeft}
        draftsUsed={draftsCount.count ?? 0}
        trialDraftsLimit={tenant.data?.trial_drafts_limit ?? TRIAL_DRAFTS_LIMIT}
        hasSubscription={tenant.data?.stripe_customer_id != null}
        billingEnabled={tenant.data?.billing_enabled ?? false}
      />
    </div>
  );
}
