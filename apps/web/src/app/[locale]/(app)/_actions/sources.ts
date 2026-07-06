"use server";

import { getInternal, type InternalResult, postInternal } from "@/lib/api/internal";
import { getUserAndTenant } from "@/lib/auth/tenant";
import type { AdapterDescriptor } from "@/lib/sources/adapters";
import { ADAPTER_DEFAULTS } from "@/lib/sources/adapterDefaults";

export interface SourceTestInput {
  type: string;
  url: string;
  config: Record<string, unknown>;
}

// BFF: dry-run адаптера. tenant_id с сервера. Таймаут 20с (у API свой лимит 15с).
export const testSource = async (
  input: SourceTestInput,
  locale: string,
): Promise<InternalResult<unknown>> => {
  const { tenantId } = await getUserAndTenant(locale);
  return postInternal(
    "/internal/sources/test",
    { type: input.type, url: input.url, config: input.config, tenant_id: tenantId },
    { timeoutMs: 20000 },
  );
};

// BFF: описание адаптеров. При недоступности эндпоинта — fallback-константы (де-риск секвенса).
export const getAdapters = async (locale: string): Promise<AdapterDescriptor[]> => {
  await getUserAndTenant(locale);
  const result = await getInternal<{ adapters: AdapterDescriptor[] }>("/internal/adapters", {
    timeoutMs: 5000,
  });
  if (!result.ok || !Array.isArray(result.data.adapters) || result.data.adapters.length === 0) {
    return ADAPTER_DEFAULTS;
  }
  return result.data.adapters;
};
