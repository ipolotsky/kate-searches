import { getTranslations, setRequestLocale } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";
import { RelevancePanel } from "@/components/article/RelevancePanel";
import { ScoreFeedback } from "@/components/article/ScoreFeedback";
import { SourceOriginal } from "@/components/article/SourceOriginal";
import { ArrowLeftIcon } from "@/components/ui/icons";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { createClient } from "@/lib/supabase/server";
import { type ArticleOriginal, type SourceRef, parseRelevance } from "@/lib/types";

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("source");
  await getUserAndTenant(locale);
  const supabase = await createClient();

  const articleResult = await supabase
    .from("articles")
    .select("id, url, title, body, summary, author, published_at, language, relevance, source_id")
    .eq("id", id)
    .maybeSingle();
  if (articleResult.data == null) {
    notFound();
  }
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
  const relevance = parseRelevance(row.relevance);

  let source: SourceRef | null = null;
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

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <Link
        href={`/${locale}/dashboard`}
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:underline"
      >
        <ArrowLeftIcon className="h-4 w-4" />
        {t("back")}
      </Link>
      <SourceOriginal article={original} source={source} />
      {relevance != null ? <RelevancePanel relevance={relevance} /> : null}
      <ScoreFeedback articleId={row.id} locale={locale} />
    </div>
  );
}
