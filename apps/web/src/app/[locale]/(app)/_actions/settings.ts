"use server";

import { revalidatePath } from "next/cache";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { TRIAL_SOURCES_LIMIT } from "@/lib/plans";
import type { Json } from "@/lib/supabase/database.types";
import { createClient } from "@/lib/supabase/server";
import type { VoiceExample } from "@/lib/types";

export interface ActionResult {
  ok: boolean;
  code?: string;
}

export interface BrandProfileInput {
  companyDescription: string;
  audienceDescription: string;
  filterCriteria: string;
  voiceConfig: Record<string, unknown>;
  voiceExamples: VoiceExample[];
  scoreThreshold: number;
  locales: string[];
}

const orNull = (value: string): string | null => (value.trim().length > 0 ? value : null);

// Upsert бренд-профиля по tenant_id (unique). tenant_id ставится на сервере (WITH CHECK, нет дефолта).
// Неуказанные колонки (criteria_weights, files) на update сохраняются, на первом insert — дефолт.
export const upsertBrandProfile = async (
  input: BrandProfileInput,
  locale: string,
): Promise<ActionResult> => {
  const { tenantId } = await getUserAndTenant(locale);
  const supabase = await createClient();
  const result = await supabase.from("brand_profiles").upsert(
    {
      tenant_id: tenantId,
      company_description: orNull(input.companyDescription),
      audience_description: orNull(input.audienceDescription),
      filter_criteria: orNull(input.filterCriteria),
      voice_config: input.voiceConfig as unknown as Json,
      voice_examples: input.voiceExamples as unknown as Json,
      score_threshold: input.scoreThreshold,
      locales: input.locales,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "tenant_id" },
  );
  if (result.error != null) {
    return { ok: false, code: "saveFailed" };
  }
  revalidatePath(`/${locale}/settings`);
  return { ok: true };
};

export interface SourceInput {
  id: string | null;
  type: string;
  url: string;
  title: string;
  category: string;
  priority: number;
  config: Record<string, unknown>;
  enabled: boolean;
}

// Insert (новый источник, tenant_id с сервера) или update существующего (скоуп по id под RLS).
export const upsertSource = async (
  input: SourceInput,
  locale: string,
): Promise<ActionResult> => {
  const { tenantId } = await getUserAndTenant(locale);
  const supabase = await createClient();

  // Триал: value-fence по числу источников (ограничивает объём scoring). Только на новый источник.
  if (input.id == null) {
    const tenant = await supabase
      .from("tenants")
      .select("subscription_status, trial_sources_limit")
      .eq("id", tenantId)
      .maybeSingle();
    if (tenant.data?.subscription_status === "trialing") {
      const limit = tenant.data.trial_sources_limit ?? TRIAL_SOURCES_LIMIT;
      const count = await supabase.from("sources").select("id", { count: "exact", head: true });
      if ((count.count ?? 0) >= limit) {
        return { ok: false, code: "trialSourcesLimit" };
      }
    }
  }

  const base = {
    type: input.type,
    url: input.url,
    title: orNull(input.title),
    category: orNull(input.category),
    priority: input.priority,
    config: input.config as unknown as Json,
    enabled: input.enabled,
  };
  const result =
    input.id != null
      ? await supabase.from("sources").update(base).eq("id", input.id)
      : await supabase.from("sources").insert({ ...base, tenant_id: tenantId });
  if (result.error != null) {
    return { ok: false, code: "saveFailed" };
  }
  revalidatePath(`/${locale}/settings`);
  return { ok: true };
};

export const deleteSource = async (id: string, locale: string): Promise<ActionResult> => {
  await getUserAndTenant(locale);
  const supabase = await createClient();
  const result = await supabase.from("sources").delete().eq("id", id);
  if (result.error != null) {
    return { ok: false, code: "deleteFailed" };
  }
  revalidatePath(`/${locale}/settings`);
  return { ok: true };
};
