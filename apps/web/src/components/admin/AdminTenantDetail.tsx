"use client";

import {
  Badge,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
} from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { PlanBudgetForm } from "@/components/admin/PlanBudgetForm";
import { ArrowLeftIcon } from "@/components/ui/icons";
import type { StageSpend } from "@/components/usage/UsageSummary";
import { RESERVED_MARGIN_PCT } from "@/lib/plans";
import { formatUsd } from "@/lib/usage";

interface AdminTenantDetailProps {
  locale: string;
  tenantId: string;
  name: string;
  plan: string;
  budget: number;
  threshold: number;
  spend: number;
  stages: StageSpend[];
  price: number | null;
  sourcesLimit: number | null;
  draftsLimit: number | null;
}

export const AdminTenantDetail: React.FC<AdminTenantDetailProps> = (props) => {
  const t = useTranslations("admin.detail");
  const tStage = useTranslations("admin.stages");
  const tForm = useTranslations("admin.form");

  const limitOrUnlimited = (value: number | null): string =>
    value != null ? String(value) : t("unlimited");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          href={`/${props.locale}/admin`}
          className="mb-2 inline-flex items-center gap-1 text-sm text-gray-500 hover:underline"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          {t("back")}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{props.name}</h1>
          <Badge color="info">{props.plan}</Badge>
        </div>
      </div>

      <Card>
        <div className="flex items-baseline justify-between">
          <span className="text-sm text-gray-500">{t("spendThisMonth")}</span>
          <span className="text-lg font-semibold text-gray-900 dark:text-white">
            {formatUsd(props.spend)} / {formatUsd(props.budget)}
          </span>
        </div>
      </Card>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">{t("byStage")}</h2>
        {props.stages.length === 0 ? (
          <p className="text-sm text-gray-500">{t("noSpend")}</p>
        ) : (
          <div className="overflow-x-auto">
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
                      {tStage(row.stage)}
                    </TableCell>
                    <TableCell>{formatUsd(row.cost)}</TableCell>
                    <TableCell>{row.calls}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">
          {t("planLimits")}
        </h2>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-500">
          <span>
            {t("price")}: {props.price != null ? formatUsd(props.price) : "—"}
          </span>
          <span>
            {t("reservedMargin")}: {RESERVED_MARGIN_PCT}%
          </span>
          <span>
            {t("sources")}: {limitOrUnlimited(props.sourcesLimit)}
          </span>
          <span>
            {t("drafts")}: {limitOrUnlimited(props.draftsLimit)}
          </span>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">
          {tForm("title")}
        </h2>
        <PlanBudgetForm
          tenantId={props.tenantId}
          locale={props.locale}
          initialPlan={props.plan}
          initialBudget={props.budget}
          initialThreshold={props.threshold}
        />
      </section>
    </div>
  );
};
