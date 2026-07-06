import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { PostEditor, type EditablePost } from "@/components/editor/PostEditor";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { createClient } from "@/lib/supabase/server";
import {
  type ArticleOriginal,
  type PostStatus,
  type RelevanceScore,
  type SourceRef,
  parseFaq,
  parseJsonLd,
  parseRelevance,
  parseSeo,
} from "@/lib/types";

export default async function PostEditorPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  await getUserAndTenant(locale);
  const supabase = await createClient();

  const postResult = await supabase.from("posts").select("*").eq("id", id).maybeSingle();
  if (postResult.data == null) {
    notFound();
  }
  const post = postResult.data;

  let article: { original: ArticleOriginal; relevance: RelevanceScore | null } | null = null;
  let source: SourceRef | null = null;

  if (post.article_id != null) {
    const articleResult = await supabase
      .from("articles")
      .select("id, url, title, body, summary, author, published_at, language, relevance, source_id")
      .eq("id", post.article_id)
      .maybeSingle();
    if (articleResult.data != null) {
      const row = articleResult.data;
      const original: ArticleOriginal = {
        id: row.id,
        url: row.url,
        title: row.title,
        body: row.body,
        summary: row.summary,
        author: row.author,
        publishedAt: row.published_at,
        language: row.language,
      };
      article = { original, relevance: parseRelevance(row.relevance) };
      if (row.source_id != null) {
        const sourceResult = await supabase
          .from("sources")
          .select("title, url")
          .eq("id", row.source_id)
          .maybeSingle();
        if (sourceResult.data != null) {
          source = { title: sourceResult.data.title, url: sourceResult.data.url };
        }
      }
    }
  }

  const editable: EditablePost = {
    id: post.id,
    title: post.title ?? "",
    bodyMarkdown: post.body_markdown ?? "",
    faq: parseFaq(post.faq),
    jsonLd: parseJsonLd(post.json_ld),
    seo: parseSeo(post.seo),
    suggestedTitles: post.suggested_titles ?? [],
    language: post.language,
    status: post.status as PostStatus,
    model: post.ai_model,
  };

  return <PostEditor post={editable} article={article} source={source} locale={locale} />;
}
