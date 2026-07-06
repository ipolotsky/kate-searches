"use client";

import { Badge } from "flowbite-react";
import { useTranslations } from "next-intl";
import { PriorityBadge } from "@/components/ui/PriorityBadge";
import { ScoreBadge } from "@/components/ui/ScoreBadge";
import { extractCriteria, isPriority, type Level, type RelevanceScore } from "@/lib/types";

interface RelevancePanelProps {
  relevance: RelevanceScore;
}

const LEVEL_COLOR: Record<Level, "gray" | "warning" | "success"> = {
  low: "gray",
  medium: "warning",
  high: "success",
};

// Имена критериев не хардкодятся: гуманизируем ключ (news_potential -> News potential).
const humanize = (key: string): string =>
  key
    .split("_")
    .map((word) => (word.length > 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(" ");

export const RelevancePanel: React.FC<RelevancePanelProps> = (props) => {
  const t = useTranslations("relevance");
  const relevance = props.relevance;
  const criteria = extractCriteria(relevance);
  const overall = typeof relevance.overall_score === "number" ? relevance.overall_score : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {overall != null ? <ScoreBadge score={overall} label={t("overall")} /> : null}
        {isPriority(relevance.publication_priority) ? (
          <PriorityBadge priority={relevance.publication_priority} />
        ) : null}
        <Badge color={relevance.passes_threshold ? "success" : "gray"}>
          {relevance.passes_threshold ? t("passes") : t("filtered")}
        </Badge>
      </div>

      {typeof relevance.decision_summary === "string" && relevance.decision_summary.length > 0 ? (
        <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {relevance.decision_summary}
        </p>
      ) : null}

      {typeof relevance.trend_explanation === "string" && relevance.trend_explanation.length > 0 ? (
        <div>
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
            {t("trend")}
          </h4>
          <p className="text-sm text-gray-700 dark:text-gray-300">{relevance.trend_explanation}</p>
        </div>
      ) : null}

      <div className="flex flex-col gap-2">
        {criteria.map((criterion) => (
          <div
            key={criterion.key}
            className="rounded-lg border border-gray-200 p-3 dark:border-gray-700"
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {humanize(criterion.key)}
              </span>
              <Badge color={LEVEL_COLOR[criterion.score]}>{t(`levels.${criterion.score}`)}</Badge>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">{criterion.reasoning}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
