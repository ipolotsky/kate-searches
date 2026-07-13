// Доменные типы и парсеры jsonb-полей. Отражают Pydantic-схемы пайплайна
// (RelevanceScore, DraftPost) и колонки articles/posts.

export type Level = "low" | "medium" | "high";
export type Priority = "HOT" | "WARM" | "COLD" | "DROP";
export type PostStatus = "new" | "in_progress" | "published" | "rejected" | "archived";
export type ArticleStatus =
  | "new"
  | "extracted"
  | "filtered_out"
  | "scored"
  | "drafting"
  | "drafted"
  | "duplicate";

export const LEVEL_ORDER: Record<Level, number> = { low: 0, medium: 1, high: 2 };
export const PRIORITIES: Priority[] = ["HOT", "WARM", "COLD", "DROP"];
export const POST_STATUSES: PostStatus[] = [
  "new",
  "in_progress",
  "published",
  "rejected",
  "archived",
];

export interface CriterionScore {
  reasoning: string;
  score: Level;
}

export interface CriterionEntry extends CriterionScore {
  key: string;
}

// Полный RelevanceScore (articles.relevance). Критерии перечислены явно для типизации
// панелей, но RelevancePanel итерирует их динамически (extractCriteria) — без хардкода имён.
export interface RelevanceScore {
  overall_score: number;
  publication_priority: Priority;
  passes_threshold: boolean;
  trend_explanation: string;
  decision_summary: string;
  [criterion: string]: CriterionScore | number | string | boolean | Priority;
}

export interface PostSeo {
  meta_description?: string;
  keywords?: string[];
  entities?: string[];
  brand_tie_in?: string;
  seo_instructions?: string;
}

export interface FaqItem {
  question: string;
  answer: string;
}

export interface VoiceExample {
  post_text: string;
  source_url: string;
  why: string;
}

export interface SourceRef {
  title: string | null;
  url: string;
}

// View-model поста для дашборда/карточки (маппится из posts + article + source).
export interface PostView {
  id: string;
  title: string;
  status: PostStatus;
  model: string | null;
  updatedAt: string;
  priority: Priority | null;
  score: number | null;
  articleId: string | null;
  source: SourceRef | null;
}

// View-model scored-статьи без поста — кандидат на генерацию.
export interface CandidateView {
  id: string;
  title: string;
  url: string;
  score: number | null;
  priority: Priority | null;
  source: SourceRef | null;
}

// View-model строки «потока скоринга»: любая статья, прошедшая скоринг (scored/filtered_out/drafted),
// со скором, приоритетом, исходом гейта (passed) и человекочитаемой причиной (decision_summary).
export interface FeedItemView {
  id: string;
  title: string;
  url: string;
  status: ArticleStatus;
  score: number | null;
  priority: Priority | null;
  passed: boolean;
  reason: string;
  source: SourceRef | null;
}

// View-model источника для настроек (строка + здоровье).
export interface SourceView {
  id: string;
  type: string;
  url: string;
  title: string | null;
  category: string | null;
  priority: number;
  config: Record<string, unknown>;
  enabled: boolean;
  lastStatus: string | null;
  lastError: string | null;
  lastRunAt: string | null;
}

// Исходник новости для SourceOriginal (та же панель в редакторе и на articles/[id]).
export interface ArticleOriginal {
  id: string;
  url: string;
  title: string | null;
  body: string | null;
  summary: string | null;
  author: string | null;
  publishedAt: string | null;
  language: string | null;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value != null && !Array.isArray(value);

export const isCriterionScore = (value: unknown): value is CriterionScore =>
  isRecord(value) &&
  typeof value.reasoning === "string" &&
  (value.score === "low" || value.score === "medium" || value.score === "high");

// Критерии релевантности как список пар {key, reasoning, score} — для итерации в UI.
export const extractCriteria = (relevance: unknown): CriterionEntry[] => {
  if (!isRecord(relevance)) {
    return [];
  }
  return Object.entries(relevance)
    .filter((entry): entry is [string, CriterionScore] => isCriterionScore(entry[1]))
    .map(([key, value]) => ({ key, reasoning: value.reasoning, score: value.score }));
};

export const parseRelevance = (value: unknown): RelevanceScore | null => {
  if (!isRecord(value)) {
    return null;
  }
  return value as RelevanceScore;
};

export const parseSeo = (value: unknown): PostSeo => {
  if (!isRecord(value)) {
    return {};
  }
  return value as PostSeo;
};

export const parseFaq = (value: unknown): FaqItem[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (x): x is FaqItem =>
      isRecord(x) && typeof x.question === "string" && typeof x.answer === "string",
  );
};

export const parseJsonLd = (value: unknown): Record<string, unknown> | null => {
  if (!isRecord(value)) {
    return null;
  }
  return value;
};

export const parseVoiceExamples = (value: unknown): VoiceExample[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter(isRecord)
    .map((x) => ({
      post_text: typeof x.post_text === "string" ? x.post_text : "",
      source_url: typeof x.source_url === "string" ? x.source_url : "",
      why: typeof x.why === "string" ? x.why : "",
    }));
};

export const isPriority = (value: unknown): value is Priority =>
  value === "HOT" || value === "WARM" || value === "COLD" || value === "DROP";

// publication_priority живёт внутри articles.relevance, а не отдельной колонкой.
export const priorityOf = (relevance: unknown): Priority | null => {
  const parsed = parseRelevance(relevance);
  return parsed != null && isPriority(parsed.publication_priority)
    ? parsed.publication_priority
    : null;
};
