"use client";

import { Badge } from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { StatusSection } from "@/components/dashboard/StatusSection";
import { PriorityBadge } from "@/components/ui/PriorityBadge";
import { ScoreBadge } from "@/components/ui/ScoreBadge";
import type { FeedItemView } from "@/lib/types";

interface ArticleFeedProps {
  items: FeedItemView[];
  locale: string;
}

export const ArticleFeed: React.FC<ArticleFeedProps> = (props) => {
  const t = useTranslations("dashboard.feed");

  return (
    <StatusSection title={t("title")} count={props.items.length} defaultOpen={props.items.length > 0}>
      {props.items.length === 0 ? (
        <p className="px-1 text-sm text-gray-500">{t("empty")}</p>
      ) : (
        <ul className="divide-y divide-gray-100 dark:divide-gray-700">
          {props.items.map((x) => (
            <li key={x.id} className="flex items-start gap-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="mb-0.5 flex flex-wrap items-center gap-2">
                  {x.score != null ? <ScoreBadge score={x.score} /> : null}
                  {x.priority != null ? <PriorityBadge priority={x.priority} /> : null}
                  <Badge color={x.passed ? "success" : "gray"}>
                    {x.passed ? t("passed") : t("filtered")}
                  </Badge>
                </div>
                <Link
                  href={`/${props.locale}/articles/${x.id}`}
                  className="block truncate text-sm font-medium text-gray-900 hover:underline dark:text-white"
                >
                  {x.title.length > 0 ? x.title : x.url}
                </Link>
                {x.reason.length > 0 ? (
                  <p className="line-clamp-2 text-xs text-gray-500">{x.reason}</p>
                ) : null}
                {x.source != null ? (
                  <span className="text-xs text-gray-400">{x.source.title ?? x.source.url}</span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </StatusSection>
  );
};
