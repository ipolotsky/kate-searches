"use server";

import { getUserAndTenant } from "@/lib/auth/tenant";
import { isPlan } from "@/lib/plans";
import {
  TRIAL_DAYS,
  appBaseUrl,
  isStripeConfigured,
  priceIdForPlan,
} from "@/lib/stripe/config";
import { stripe } from "@/lib/stripe/client";
import { createAdminClient } from "@/lib/supabase/admin";

export interface BillingActionResult {
  ok: boolean;
  code?: string;
  url?: string;
}

// Старт триала через Stripe Checkout (card-first, native trial_period_days). Гейт allowlist:
// только billing_enabled тенанты доходят до Checkout (в test-mode — приглашённые). client_reference_id
// и subscription metadata несут tenant_id — по нему вебхук провижинит план/бюджет.
export const startCheckout = async (
  plan: string,
  locale: string,
): Promise<BillingActionResult> => {
  const { tenantId, email } = await getUserAndTenant(locale);
  if (!isStripeConfigured()) {
    return { ok: false, code: "notConfigured" };
  }
  if (!isPlan(plan) || plan === "pilot") {
    return { ok: false, code: "invalidPlan" };
  }
  const priceId = priceIdForPlan(plan);
  if (priceId == null) {
    return { ok: false, code: "invalidPlan" };
  }

  const admin = createAdminClient();
  const tenant = await admin
    .from("tenants")
    .select("billing_enabled, stripe_customer_id")
    .eq("id", tenantId)
    .single();
  if (tenant.error != null) {
    return { ok: false, code: "failed" };
  }
  if (!tenant.data.billing_enabled) {
    return { ok: false, code: "billingDisabled" };
  }

  const customerId = tenant.data.stripe_customer_id;
  try {
    const session = await stripe().checkout.sessions.create({
      mode: "subscription",
      line_items: [{ price: priceId, quantity: 1 }],
      client_reference_id: tenantId,
      customer: customerId ?? undefined,
      customer_email: customerId == null ? email : undefined,
      subscription_data: {
        trial_period_days: TRIAL_DAYS,
        metadata: { tenant_id: tenantId },
      },
      metadata: { tenant_id: tenantId },
      success_url: `${appBaseUrl()}/${locale}/billing?checkout=success`,
      cancel_url: `${appBaseUrl()}/${locale}/billing?checkout=cancel`,
    });
    if (session.url == null) {
      return { ok: false, code: "failed" };
    }
    return { ok: true, url: session.url };
  } catch {
    return { ok: false, code: "failed" };
  }
};

// Self-serve управление подпиской (смена тира, карта, отмена) — стандартный Stripe Billing Portal.
export const openBillingPortal = async (locale: string): Promise<BillingActionResult> => {
  const { tenantId } = await getUserAndTenant(locale);
  if (!isStripeConfigured()) {
    return { ok: false, code: "notConfigured" };
  }
  const admin = createAdminClient();
  const tenant = await admin
    .from("tenants")
    .select("stripe_customer_id")
    .eq("id", tenantId)
    .single();
  if (tenant.error != null || tenant.data.stripe_customer_id == null) {
    return { ok: false, code: "noCustomer" };
  }
  try {
    const session = await stripe().billingPortal.sessions.create({
      customer: tenant.data.stripe_customer_id,
      return_url: `${appBaseUrl()}/${locale}/billing`,
    });
    return { ok: true, url: session.url };
  } catch {
    return { ok: false, code: "failed" };
  }
};
