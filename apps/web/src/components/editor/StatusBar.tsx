"use client";

import { Badge } from "flowbite-react";
import { useTranslations } from "next-intl";
import { StatusActionButtons } from "@/components/ui/StatusActionButtons";
import type { PostStatus } from "@/lib/types";

interface StatusBarProps {
  status: PostStatus;
  pending: boolean;
  onChange: (next: PostStatus) => void;
}

const STATUS_COLOR: Record<PostStatus, "info" | "warning" | "success" | "failure" | "gray"> = {
  new: "info",
  in_progress: "warning",
  published: "success",
  rejected: "failure",
  archived: "gray",
};

export const StatusBar: React.FC<StatusBarProps> = (props) => {
  const t = useTranslations();

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-gray-500">{t("editor.status")}</span>
      <Badge color={STATUS_COLOR[props.status]}>{t(`dashboard.statuses.${props.status}`)}</Badge>
      <span className="mx-1 h-4 w-px bg-gray-200 dark:bg-gray-700" />
      <StatusActionButtons
        status={props.status}
        pending={props.pending}
        onChange={props.onChange}
        size="sm"
      />
    </div>
  );
};
