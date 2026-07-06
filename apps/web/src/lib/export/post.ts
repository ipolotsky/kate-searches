import type { FaqItem, PostSeo } from "@/lib/types";

// Общая форма поста для экспортных билдеров. Билдеры чистые (string -> string),
// без DOM/сети — тестируются юнитами.
export interface ExportablePost {
  title: string;
  bodyMarkdown: string;
  faq: FaqItem[];
  jsonLd: Record<string, unknown> | null;
  seo: PostSeo;
  suggestedTitles: string[];
  language: string | null;
}
