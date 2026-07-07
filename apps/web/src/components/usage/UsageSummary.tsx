"use client";

import {
  Badge,
  Card,
  Progress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
} from "flowbite-react";
import { useTranslations } from "next-intl";
import { type UsageLevel, formatUsd } from "@/lib/usage";

export interface StageSpend {
  stage: string;
  cost: number;
  calls: number;
}

interface UsageSummaryProps {
  plan: string;
  spend: number;
  budget: number;
  percent: number;
  level: UsageLevel;
  draftsThisMonth: number;
  stages: StageSpend[];
  sourcesLimit: number | null;
  draftsLimit: number | null;
}

const PROGRESS_COLOR: Record<UsageLevel, "green" | "yellow" | "red"> = {
  ok: "green",
  notice: "yellow",
  upsell: "yellow",
  blocked: "red",
};

export const UsageSummary: React.FC<UsageSummaryProps> = (props) => {
  const t = useTranslations("usage");

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-gray-400">{t("plan")}</p>
            <Badge color="info" className="mt-1 inline-block">
              {props.plan}
            </Badge>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-gray-400">{t("draftsThisMonth")}</p>
            <p className="text-lg font-semibold text-gray-900 dark:text-white">
              {props.draftsThisMonth}
            </p>
          </div>
        </div>

        <div>
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-sm text-gray-500">{t("spend")}</span>
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {formatUsd(props.spend)} / {formatUsd(props.budget)}
            </span>
          </div>
          <Progress progress={props.percent} color={PROGRESS_COLOR[props.level]} size="lg" />
          <p className="mt-1 text-xs text-gray-400">
            {t("percentUsed", { percent: props.percent })}
          </p>
        </div>

        {props.sourcesLimit != null || props.draftsLimit != null ? (
          <div className="flex flex-wrap gap-4 border-t border-gray-100 pt-3 text-xs text-gray-400 dark:border-gray-700">
            <span className="font-medium">{t("limits.title")}:</span>
            <span>
              {t("limits.sources", {
                value: props.sourcesLimit != null ? props.sourcesLimit : t("limits.unlimited"),
              })}
            </span>
            <span>
              {t("limits.drafts", {
                value: props.draftsLimit != null ? props.draftsLimit : t("limits.unlimited"),
              })}
            </span>
          </div>
        ) : null}
      </Card>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">{t("byStage")}</h2>
        {props.stages.length === 0 ? (
          <p className="text-sm text-gray-500">{t("noSpend")}</p>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeadCell>{t("stage")}</TableHeadCell>
                <TableHeadCell>{t("cost")}</TableHeadCell>
                <TableHeadCell>{t("calls")}</TableHeadCell>
              </TableRow>
            </TableHead>
            <TableBody className="divide-y">
              {props.stages.map((row) => (
                <TableRow key={row.stage} className="bg-white dark:bg-gray-800">
                  <TableCell className="font-medium text-gray-900 dark:text-white">
                    {t(`stages.${row.stage}`)}
                  </TableCell>
                  <TableCell>{formatUsd(row.cost)}</TableCell>
                  <TableCell>{row.calls}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  );
};
