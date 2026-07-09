"use server";

import { revalidatePath } from "next/cache";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { canTransition } from "@/lib/posts/status";
import type { Database, Json } from "@/lib/supabase/database.types";
import { createClient } from "@/lib/supabase/server";
import type { FaqItem, PostSeo, PostStatus } from "@/lib/types";

export interface ActionResult {
  ok: boolean;
  code?: string;
}

type PostUpdate = Database["public"]["Tables"]["posts"]["Update"];

// Доменный patch: клиент шлёт типизированные структуры, Json-каст к колонкам делается здесь.
export interface PostPatch {
  title?: string;
  body_markdown?: string;
  faq?: FaqItem[];
  json_ld?: Record<string, unknown> | null;
  seo?: PostSeo;
  suggested_titles?: string[];
  language?: string | null;
}

const toUpdate = (patch: PostPatch): PostUpdate => {
  const update: PostUpdate = { updated_at: new Date().toISOString() };
  if (patch.title !== undefined) {
    update.title = patch.title;
  }
  if (patch.body_markdown !== undefined) {
    update.body_markdown = patch.body_markdown;
  }
  if (patch.faq !== undefined) {
    update.faq = patch.faq as unknown as Json;
  }
  if (patch.json_ld !== undefined) {
    update.json_ld = patch.json_ld as unknown as Json;
  }
  if (patch.seo !== undefined) {
    update.seo = patch.seo as unknown as Json;
  }
  if (patch.suggested_titles !== undefined) {
    update.suggested_titles = patch.suggested_titles;
  }
  if (patch.language !== undefined) {
    update.language = patch.language;
  }
  return update;
};

// Смена статуса поста: легальность перехода проверяется до UPDATE. RLS скоупит строку к тенанту.
export const updatePostStatus = async (
  postId: string,
  next: PostStatus,
  locale: string,
): Promise<ActionResult> => {
  await getUserAndTenant(locale);
  const supabase = await createClient();

  const current = await supabase.from("posts").select("status").eq("id", postId).maybeSingle();
  if (current.error != null || current.data == null) {
    return { ok: false, code: "notFound" };
  }

  const from = current.data.status as PostStatus;
  if (!canTransition(from, next)) {
    return { ok: false, code: "illegalTransition" };
  }

  // Compare-and-swap: пишем, только если статус всё ещё `from`. Конкурентный легальный переход
  // (две вкладки / быстрые клики) успевает сдвинуть строку между read и write — без .eq("status")
  // мы бы записали поверх устаревшей проверки canTransition и получили запрещённое состояние.
  const updated = await supabase
    .from("posts")
    .update({ status: next, updated_at: new Date().toISOString() })
    .eq("id", postId)
    .eq("status", from)
    .select("id");
  if (updated.error != null) {
    return { ok: false, code: "updateFailed" };
  }
  if (updated.data == null || updated.data.length === 0) {
    // Ноль затронутых строк: статус увели конкурентно — переход устарел.
    return { ok: false, code: "conflict" };
  }

  revalidatePath(`/${locale}/dashboard`);
  revalidatePath(`/${locale}/posts/${postId}`);
  return { ok: true };
};

// Сохранение контента поста (без статуса — статус идёт через updatePostStatus). RLS UPDATE.
export const savePost = async (
  postId: string,
  patch: PostPatch,
  locale: string,
): Promise<ActionResult> => {
  await getUserAndTenant(locale);
  const supabase = await createClient();

  const updated = await supabase.from("posts").update(toUpdate(patch)).eq("id", postId);
  if (updated.error != null) {
    return { ok: false, code: "updateFailed" };
  }

  revalidatePath(`/${locale}/posts/${postId}`);
  revalidatePath(`/${locale}/dashboard`);
  return { ok: true };
};
