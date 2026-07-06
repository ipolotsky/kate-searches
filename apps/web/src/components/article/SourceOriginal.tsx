"use client";

import { useLocale, useTranslations } from "next-intl";
import { ExternalLinkIcon } from "@/components/ui/icons";
import type { ArticleOriginal, SourceRef } from "@/lib/types";

interface SourceOriginalProps {
  article: ArticleOriginal;
  source: SourceRef | null;
}

export const SourceOriginal: React.FC<SourceOriginalProps> = (props) => {
  const t = useTranslations("source");
  const locale = useLocale();
  const article = props.article;

  const publishedLabel =
    article.publishedAt != null
      ? new Date(article.publishedAt).toLocaleDateString(locale, {
          year: "numeric",
          month: "short",
          day: "numeric",
          timeZone: "UTC",
        })
      : null;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-base font-semibold text-gray-900 dark:text-white">
          {article.title != null && article.title.length > 0 ? article.title : article.url}
        </h3>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
          {props.source != null ? (
            <span>{props.source.title ?? props.source.url}</span>
          ) : null}
          {publishedLabel != null ? <span>{publishedLabel}</span> : null}
          {article.author != null && article.author.length > 0 ? (
            <span>{article.author}</span>
          ) : null}
        </div>
        <a
          href={article.url}
          target="_blank"
          rel="noreferrer"
          className="mt-1 inline-flex items-center gap-1 text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          {t("open")}
          <ExternalLinkIcon className="h-3.5 w-3.5" />
        </a>
      </div>

      {article.summary != null && article.summary.length > 0 ? (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
            {t("summary")}
          </h4>
          <p className="text-sm text-gray-700 dark:text-gray-300">{article.summary}</p>
        </div>
      ) : null}

      {article.body != null && article.body.length > 0 ? (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
            {t("body")}
          </h4>
          <div className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-300">
            {article.body}
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-400">{t("noBody")}</p>
      )}
    </div>
  );
};
