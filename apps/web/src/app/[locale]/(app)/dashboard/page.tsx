import { getTranslations, setRequestLocale } from "next-intl/server";
import { ArticleFeed } from "@/components/dashboard/ArticleFeed";
import { DraftsBoard } from "@/components/dashboard/DraftsBoard";
import { RunPipelineButton } from "@/components/dashboard/RunPipelineButton";
import { ScoredCandidates } from "@/components/dashboard/ScoredCandidates";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { createClient } from "@/lib/supabase/server";
import {
  type ArticleStatus,
  type CandidateView,
  type FeedItemView,
  type PostStatus,
  type PostView,
  type SourceRef,
  parseRelevance,
  priorityOf,
} from "@/lib/types";

const oneOf = <T,>(value: T | T[] | null): T | null =>
  Array.isArray(value) ? (value[0] ?? null) : value;

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("dashboard");
  await getUserAndTenant(locale);
  const supabase = await createClient();

  const postsResult = await supabase
    .from("posts")
    .select(
      "id, title, status, ai_model, updated_at, article_id, articles(id, relevance_score, relevance, source_id)",
    )
    .order("created_at", { ascending: false });
  if (postsResult.error != null) {
    throw new Error(postsResult.error.message);
  }
  const postRows = postsResult.data ?? [];

  const candidatesResult = await supabase
    .from("articles")
    .select("id, url, title, relevance_score, relevance, source_id")
    .eq("status", "scored")
    .order("relevance_score", { ascending: false, nullsFirst: false });
  if (candidatesResult.error != null) {
    throw new Error(candidatesResult.error.message);
  }
  const candidateRows = candidatesResult.data ?? [];

  const feedResult = await supabase
    .from("articles")
    .select("id, url, title, status, relevance_score, relevance, source_id")
    .not("relevance_score", "is", null)
    .order("published_at", { ascending: false, nullsFirst: false })
    .limit(60);
  if (feedResult.error != null) {
    throw new Error(feedResult.error.message);
  }
  const feedRows = feedResult.data ?? [];

  const draftedArticleIds = new Set(
    postRows.map((x) => x.article_id).filter((x): x is string => x != null),
  );

  const sourceIds = [
    ...new Set(
      [
        ...postRows.map((x) => oneOf(x.articles)?.source_id),
        ...candidateRows.map((x) => x.source_id),
        ...feedRows.map((x) => x.source_id),
      ].filter((x): x is string => x != null),
    ),
  ];
  const sourcesResult =
    sourceIds.length > 0
      ? await supabase.from("sources").select("id, title, url").in("id", sourceIds)
      : { data: [] };
  const sourceById = new Map<string, SourceRef>(
    (sourcesResult.data ?? []).map((x) => [x.id, { title: x.title, url: x.url }]),
  );

  const posts: PostView[] = postRows.map((row) => {
    const article = oneOf(row.articles);
    return {
      id: row.id,
      title: row.title ?? "",
      status: row.status as PostStatus,
      model: row.ai_model,
      updatedAt: row.updated_at,
      priority: priorityOf(article?.relevance),
      score: article?.relevance_score ?? null,
      articleId: article?.id ?? null,
      source: article?.source_id != null ? (sourceById.get(article.source_id) ?? null) : null,
    };
  });

  const candidates: CandidateView[] = candidateRows
    .filter((row) => !draftedArticleIds.has(row.id))
    .map((row) => ({
      id: row.id,
      title: row.title ?? "",
      url: row.url,
      score: row.relevance_score,
      priority: priorityOf(row.relevance),
      source: row.source_id != null ? (sourceById.get(row.source_id) ?? null) : null,
    }));

  const feed: FeedItemView[] = feedRows.map((row) => {
    const relevance = parseRelevance(row.relevance);
    return {
      id: row.id,
      title: row.title ?? "",
      url: row.url,
      status: row.status as ArticleStatus,
      score: row.relevance_score,
      priority: priorityOf(row.relevance),
      passed: row.status !== "filtered_out",
      reason: relevance?.decision_summary ?? "",
      source: row.source_id != null ? (sourceById.get(row.source_id) ?? null) : null,
    };
  });

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t("title")}</h1>
          <p className="text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <RunPipelineButton locale={locale} />
      </div>

      <ScoredCandidates candidates={candidates} locale={locale} />
      <DraftsBoard posts={posts} locale={locale} />
      <ArticleFeed items={feed} locale={locale} />
    </div>
  );
}
