import type Stripe from "stripe";
import { beforeEach, describe, expect, it } from "vitest";
import { tenantIdFromSubscription, tenantUpdateForSubscription } from "./provisioning";

const subscription = (overrides: Partial<Stripe.Subscription>): Stripe.Subscription =>
  ({
    id: "sub_1",
    status: "trialing",
    trial_end: 1_800_000_000,
    metadata: { tenant_id: "t-1" },
    items: { data: [{ price: { id: "price_pro_x" }, current_period_end: 1_800_000_500 }] },
    ...overrides,
  }) as unknown as Stripe.Subscription;

describe("tenantUpdateForSubscription", () => {
  beforeEach(() => {
    process.env.STRIPE_PRICE_STARTER = "price_starter_x";
    process.env.STRIPE_PRICE_PRO = "price_pro_x";
    process.env.STRIPE_PRICE_AGENCY = "price_agency_x";
  });

  it("trialing: план тира, но триальный бюджет $3", () => {
    const update = tenantUpdateForSubscription(subscription({ status: "trialing" }));
    expect(update.subscription_status).toBe("trialing");
    expect(update.plan).toBe("pro");
    expect(update.ai_budget_usd_month).toBe(3);
    expect(update.trial_ends_at).not.toBeNull();
  });

  it("active: бюджет тира (usable из каталога)", () => {
    const update = tenantUpdateForSubscription(subscription({ status: "active" }));
    expect(update.plan).toBe("pro");
    expect(update.ai_budget_usd_month).toBe(103.2);
  });

  it("canceled: даунгрейд в pilot, бюджет 0", () => {
    const update = tenantUpdateForSubscription(subscription({ status: "canceled" }));
    expect(update.plan).toBe("pilot");
    expect(update.ai_budget_usd_month).toBe(0);
  });

  it("past_due: план/бюджет не трогаем (доступ держим)", () => {
    const update = tenantUpdateForSubscription(subscription({ status: "past_due" }));
    expect(update.subscription_status).toBe("past_due");
    expect(update.plan).toBeUndefined();
    expect(update.ai_budget_usd_month).toBeUndefined();
  });

  it("tenant_id из metadata подписки", () => {
    expect(tenantIdFromSubscription(subscription({}))).toBe("t-1");
  });
});
