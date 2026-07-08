// Маппинг подписки Stripe -> обновление строки tenants. Stripe — источник правды по плану/статусу,
// мост в наш enforcement (ledger) — одно число ai_budget_usd_month. Чистая функция, тестируется
// без Stripe/БД. status: trialing | active | past_due | canceled | unpaid | ...

import type Stripe from "stripe";
import type { Database } from "@/lib/supabase/database.types";
import { TRIAL_BUDGET_USD, budgetForPlan, planForPriceId } from "./config";

type TenantUpdate = Database["public"]["Tables"]["tenants"]["Update"];

const unixToIso = (value: number | null | undefined): string | null =>
  value != null ? new Date(value * 1000).toISOString() : null;

// current_period_end в разных версиях Stripe API лежит либо на подписке, либо на её item.
const currentPeriodEndUnix = (subscription: Stripe.Subscription): number | null => {
  const item = subscription.items?.data?.[0] as { current_period_end?: number } | undefined;
  const top = (subscription as unknown as { current_period_end?: number }).current_period_end;
  return item?.current_period_end ?? top ?? null;
};

export const tenantIdFromSubscription = (subscription: Stripe.Subscription): string | null =>
  subscription.metadata?.tenant_id ?? null;

export const tenantUpdateForSubscription = (subscription: Stripe.Subscription): TenantUpdate => {
  const status = subscription.status;
  const priceId = subscription.items?.data?.[0]?.price?.id ?? null;
  const plan = priceId != null ? planForPriceId(priceId) : null;

  const update: TenantUpdate = {
    stripe_subscription_id: subscription.id,
    subscription_status: status,
    current_period_end: unixToIso(currentPeriodEndUnix(subscription)),
    trial_ends_at: unixToIso(subscription.trial_end),
  };

  if (status === "trialing") {
    // На триале план ставим выбранный тир, но бюджет — триальный cap (страховка COGS до конверсии).
    if (plan != null) {
      update.plan = plan;
    }
    update.ai_budget_usd_month = TRIAL_BUDGET_USD;
  } else if (status === "active") {
    // Триал сконвертился (первый invoice оплачен): бюджет тира.
    if (plan != null) {
      update.plan = plan;
      update.ai_budget_usd_month = budgetForPlan(plan);
    }
  } else if (status === "canceled" || status === "unpaid") {
    // Нет активной подписки: даунгрейд в pilot, бюджет 0 (usage не жжём).
    update.plan = "pilot";
    update.ai_budget_usd_month = 0;
  }
  // past_due: доступ держим (план/бюджет не трогаем), уведомляем отдельно (M6.3).

  return update;
};
