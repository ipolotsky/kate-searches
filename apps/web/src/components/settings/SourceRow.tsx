"use client";

import { Badge, Button } from "flowbite-react";
import { useLocale, useTranslations } from "next-intl";
import { ConfirmButton } from "@/components/ui/ConfirmButton";
import { ExternalLinkIcon } from "@/components/ui/icons";
import type { SourceView } from "@/lib/types";

interface SourceRowProps {
  source: SourceView;
  deleting: boolean;
  onEdit: () => void;
  onDelete: () => void;
}

export const SourceRow: React.FC<SourceRowProps> = (props) => {
  const t = useTranslations("sources");
  const locale = useLocale();
  const source = props.source;
  const lastRun =
    source.lastRunAt != null
      ? new Date(source.lastRunAt).toLocaleDateString(locale, { timeZone: "UTC" })
      : null;

  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-700">
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <Badge color="gray">{source.type}</Badge>
          <Badge color={source.enabled ? "success" : "gray"}>
            {source.enabled ? t("on") : t("off")}
          </Badge>
          {source.lastStatus != null ? (
            <Badge color={source.lastStatus === "ok" ? "success" : "warning"}>
              {source.lastStatus}
            </Badge>
          ) : null}
        </div>
        <p className="truncate font-medium text-gray-900 dark:text-white">
          {source.title != null && source.title.length > 0 ? source.title : source.url}
        </p>
        <a
          href={source.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 truncate text-xs text-blue-600 hover:underline dark:text-blue-400"
        >
          {source.url}
          <ExternalLinkIcon className="h-3 w-3 shrink-0" />
        </a>
        {source.lastError != null && source.lastError.length > 0 ? (
          <p className="truncate text-xs text-red-500">{source.lastError}</p>
        ) : null}
        {lastRun != null ? (
          <p className="text-xs text-gray-400">{t("lastRun", { date: lastRun })}</p>
        ) : null}
      </div>
      <div className="flex gap-2">
        <Button size="xs" color="light" disabled={props.deleting} onClick={props.onEdit}>
          {t("edit")}
        </Button>
        <ConfirmButton
          label={t("delete")}
          title={t("confirmDelete.title")}
          message={t("confirmDelete.message")}
          confirmLabel={t("confirmDelete.confirm")}
          cancelLabel={t("confirmDelete.cancel")}
          color="failure"
          disabled={props.deleting}
          onConfirm={props.onDelete}
        />
      </div>
    </div>
  );
};
