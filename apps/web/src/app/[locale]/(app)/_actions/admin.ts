"use server";

import { revalidatePath } from "next/cache";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { isPlatformAdmin } from "@/lib/auth/platform";
import { isPlan } from "@/lib/plans";
import { createAdminClient } from "@/lib/supabase/admin";

export interface AdminActionResult {
  ok: boolean;
  code?: string;
}

export interface UpdateTenantPlanInput {
  tenantId: string;
  plan: string;
  budget: number;
  upsellThresholdPct: number;
}

// Меняет тариф/бюджет/порог тенанта под service_role (control-таблица tenants writable только им).
// Гейт платформенного админа проверяется независимо — не полагаемся на то, что зовут только из admin-UI.
export const updateTenantPlan = async (
  input: UpdateTenantPlanInput,
  locale: string,
): Promise<AdminActionResult> => {
  const { userId } = await getUserAndTenant(locale);
  if (!(await isPlatformAdmin(userId))) {
    return { ok: false, code: "forbidden" };
  }

  if (!isPlan(input.plan)) {
    return { ok: false, code: "invalidPlan" };
  }
  if (!Number.isFinite(input.budget) || input.budget < 0) {
    return { ok: false, code: "invalidBudget" };
  }
  if (
    !Number.isInteger(input.upsellThresholdPct) ||
    input.upsellThresholdPct < 0 ||
    input.upsellThresholdPct > 100
  ) {
    return { ok: false, code: "invalidThreshold" };
  }

  const admin = createAdminClient();
  const result = await admin
    .from("tenants")
    .update({
      plan: input.plan,
      ai_budget_usd_month: input.budget,
      upsell_threshold_pct: input.upsellThresholdPct,
    })
    .eq("id", input.tenantId);
  if (result.error != null) {
    return { ok: false, code: "updateFailed" };
  }

  revalidatePath(`/${locale}/admin`);
  revalidatePath(`/${locale}/admin/${input.tenantId}`);
  return { ok: true };
};
