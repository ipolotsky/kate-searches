"use server";

import { revalidatePath } from "next/cache";
import { postInternal } from "@/lib/api/internal";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { createClient } from "@/lib/supabase/server";

export interface PipelineResult {
  ok: boolean;
  code?: string;
}

// BFF: дневной прогон. tenant_id резолвится на сервере, не из клиента.
// HTTP 200 не значит «поставлено»: run уже мог быть заклеймлен сегодня или enqueue упал.
export const runPipeline = async (locale: string): Promise<PipelineResult> => {
  const { tenantId } = await getUserAndTenant(locale);
  const result = await postInternal<{ queued: boolean; detail: string }>(
    "/internal/pipeline/run",
    { tenant_id: tenantId },
    { timeoutMs: 5000 },
  );
  if (!result.ok) {
    return { ok: false, code: result.code };
  }
  if (!result.data.queued) {
    const alreadyRan = result.data.detail.startsWith("run already claimed");
    return { ok: false, code: alreadyRan ? "alreadyRan" : "notQueued" };
  }
  revalidatePath(`/${locale}/dashboard`);
  return { ok: true };
};

// BFF: on-demand генерация. article_ids ре-валидируются под RLS (API не проверяет владение).
export const generateDrafts = async (
  articleIds: string[],
  locale: string,
): Promise<PipelineResult> => {
  const { tenantId } = await getUserAndTenant(locale);
  const supabase = await createClient();

  const owned = await supabase.from("articles").select("id").in("id", articleIds);
  const ownedIds = (owned.data ?? []).map((x) => x.id);
  if (ownedIds.length === 0) {
    return { ok: false, code: "noArticles" };
  }

  const result = await postInternal<{ queued: boolean; count: number }>(
    "/internal/pipeline/generate",
    { tenant_id: tenantId, article_ids: ownedIds },
    { timeoutMs: 5000 },
  );
  if (!result.ok) {
    return { ok: false, code: result.code };
  }
  // Владелец подтверждён, но статьи могли уже уйти из 'scored' (задрафчены ранее) —
  // API вернёт queued:false/count:0 с HTTP 200; это не успех.
  if (!result.data.queued || result.data.count === 0) {
    return { ok: false, code: "nothing" };
  }
  revalidatePath(`/${locale}/dashboard`);
  return { ok: true };
};
