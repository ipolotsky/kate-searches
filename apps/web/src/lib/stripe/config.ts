// Конфиг Stripe (только сервер). Режим выводится из префикса секретного ключа, а не из отдельной
// переменной — чтобы «режим» и реальные ключи не могли рассинхронизироваться. В test-mode на проде
// живут только sk_test_ ключи, поэтому live-charge невозможен by construction. Флип test->live —
// замена значений секретов (sk_/whsec_/три price_) без изменений кода.

import { PLAN_CATALOG, type Plan } from "@/lib/plans";

export const TRIAL_DAYS = 7;
export const TRIAL_BUDGET_USD = 3;

const PRICE_ENV: Record<Exclude<Plan, "pilot">, string> = {
  starter: "STRIPE_PRICE_STARTER",
  pro: "STRIPE_PRICE_PRO",
  agency: "STRIPE_PRICE_AGENCY",
};

export const stripeSecretKey = (): string => process.env.STRIPE_SECRET_KEY ?? "";

export const stripeWebhookSecret = (): string => process.env.STRIPE_WEBHOOK_SECRET ?? "";

export const isStripeConfigured = (): boolean => stripeSecretKey().length > 0;

export const isStripeTestMode = (): boolean => stripeSecretKey().startsWith("sk_test_");

export const priceIdForPlan = (plan: Plan): string | null => {
  if (plan === "pilot") {
    return null;
  }
  const value = process.env[PRICE_ENV[plan]];
  return value != null && value.length > 0 ? value : null;
};

export const planForPriceId = (priceId: string): Plan | null => {
  for (const plan of ["starter", "pro", "agency"] as const) {
    if (process.env[PRICE_ENV[plan]] === priceId) {
      return plan;
    }
  }
  return null;
};

// Бюджет активной подписки тира — usable-бюджет из каталога. На триале бюджет = TRIAL_BUDGET_USD.
export const budgetForPlan = (plan: Plan): number => PLAN_CATALOG[plan].usableBudget;

export const appBaseUrl = (): string => process.env.APP_BASE_URL ?? "http://localhost:3000";
