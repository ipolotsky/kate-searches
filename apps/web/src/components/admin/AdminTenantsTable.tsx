"use client";

import {
  Badge,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeadCell,
  TableRow,
} from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { formatUsd, usagePercent } from "@/lib/usage";

export interface TenantReportRow {
  tenant_id: string;
  name: string;
  plan: string;
  ai_budget_usd_month: number;
  upsell_threshold_pct: number;
  spend_month: number;
  drafts_month: number;
  users_count: number;
  created_at: string;
}

interface AdminTenantsTableProps {
  rows: TenantReportRow[];
  locale: string;
}

// Детерминированный формат даты (без локали/tz), чтобы не ловить hydration-mismatch.
const isoDate = (value: string): string => new Date(value).toISOString().slice(0, 10);

export const AdminTenantsTable: React.FC<AdminTenantsTableProps> = (props) => {
  const t = useTranslations("admin.table");
  const tRoot = useTranslations("admin");

  if (props.rows.length === 0) {
    return <p className="text-sm text-gray-500">{tRoot("empty")}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <Table hoverable>
        <TableHead>
          <TableRow>
            <TableHeadCell>{t("name")}</TableHeadCell>
            <TableHeadCell>{t("plan")}</TableHeadCell>
            <TableHeadCell>{t("spend")}</TableHeadCell>
            <TableHeadCell>{t("budget")}</TableHeadCell>
            <TableHeadCell>{t("percent")}</TableHeadCell>
            <TableHeadCell>{t("drafts")}</TableHeadCell>
            <TableHeadCell>{t("users")}</TableHeadCell>
            <TableHeadCell>{t("created")}</TableHeadCell>
          </TableRow>
        </TableHead>
        <TableBody className="divide-y">
          {props.rows.map((row) => (
            <TableRow key={row.tenant_id} className="bg-white dark:bg-gray-800">
              <TableCell className="font-medium text-gray-900 dark:text-white">
                <Link href={`/${props.locale}/admin/${row.tenant_id}`} className="hover:underline">
                  {row.name}
                </Link>
              </TableCell>
              <TableCell>
                <Badge color="info" className="inline-block">
                  {row.plan}
                </Badge>
              </TableCell>
              <TableCell>{formatUsd(Number(row.spend_month))}</TableCell>
              <TableCell>{formatUsd(Number(row.ai_budget_usd_month))}</TableCell>
              <TableCell>
                {usagePercent(Number(row.spend_month), Number(row.ai_budget_usd_month))}%
              </TableCell>
              <TableCell>{Number(row.drafts_month)}</TableCell>
              <TableCell>{Number(row.users_count)}</TableCell>
              <TableCell className="whitespace-nowrap text-gray-500">
                {isoDate(row.created_at)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};
