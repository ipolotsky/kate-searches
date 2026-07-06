"use server";

import { getUserAndTenant } from "@/lib/auth/tenant";
import type { EditedDiff } from "@/lib/feedback/diff";
import type { Json } from "@/lib/supabase/database.types";
import { createClient } from "@/lib/supabase/server";

export interface ActionResult {
  ok: boolean;
  code?: string;
}

interface ScoreFeedbackInput {
  articleId: string;
  rating: number | null;
  comment: string;
}

interface DraftFeedbackInput {
  postId: string;
  rating: number | null;
  comment: string;
  editedDiff: EditedDiff | null;
}

// Фидбэк по скорингу: target_type='score', target_id=article_id. RLS INSERT требует tenant_id.
export const submitScoreFeedback = async (
  input: ScoreFeedbackInput,
  locale: string,
): Promise<ActionResult> => {
  const { tenantId, userId } = await getUserAndTenant(locale);
  const supabase = await createClient();
  const inserted = await supabase.from("feedback").insert({
    tenant_id: tenantId,
    user_id: userId,
    target_type: "score",
    target_id: input.articleId,
    rating: input.rating,
    comment: input.comment.length > 0 ? input.comment : null,
  });
  if (inserted.error != null) {
    return { ok: false, code: "insertFailed" };
  }
  return { ok: true };
};

// Фидбэк по черновику: target_type='draft', target_id=post_id, edited_diff — сигнал редактуры.
export const submitDraftFeedback = async (
  input: DraftFeedbackInput,
  locale: string,
): Promise<ActionResult> => {
  const { tenantId, userId } = await getUserAndTenant(locale);
  const supabase = await createClient();
  const inserted = await supabase.from("feedback").insert({
    tenant_id: tenantId,
    user_id: userId,
    target_type: "draft",
    target_id: input.postId,
    rating: input.rating,
    comment: input.comment.length > 0 ? input.comment : null,
    edited_diff: input.editedDiff != null ? (input.editedDiff as unknown as Json) : null,
  });
  if (inserted.error != null) {
    return { ok: false, code: "insertFailed" };
  }
  return { ok: true };
};
