"use client";

import { Button } from "flowbite-react";
import { useTranslations } from "next-intl";
import { availableTransitions } from "@/lib/posts/status";
import type { PostStatus } from "@/lib/types";
import { ConfirmButton } from "./ConfirmButton";

interface StatusActionButtonsProps {
  status: PostStatus;
  pending: boolean;
  onChange: (next: PostStatus) => void;
  size?: "xs" | "sm";
}

// Кнопки легальных переходов статуса. Переиспользуются карточкой дашборда и баром редактора.
export const StatusActionButtons: React.FC<StatusActionButtonsProps> = (props) => {
  const t = useTranslations("post");
  const targets = availableTransitions(props.status);
  const size = props.size ?? "xs";

  return (
    <>
      {targets.includes("in_progress") ? (
        <Button
          size={size}
          color="light"
          disabled={props.pending}
          onClick={() => props.onChange("in_progress")}
        >
          {t("actions.take")}
        </Button>
      ) : null}

      {targets.includes("published") ? (
        <Button
          size={size}
          color="green"
          disabled={props.pending}
          onClick={() => props.onChange("published")}
        >
          {t("actions.publish")}
        </Button>
      ) : null}

      {targets.includes("new") ? (
        <Button
          size={size}
          color="light"
          disabled={props.pending}
          onClick={() => props.onChange("new")}
        >
          {t("actions.return")}
        </Button>
      ) : null}

      {targets.includes("archived") ? (
        <Button
          size={size}
          color="light"
          disabled={props.pending}
          onClick={() => props.onChange("archived")}
        >
          {t("actions.archive")}
        </Button>
      ) : null}

      {targets.includes("rejected") ? (
        <ConfirmButton
          label={t("actions.reject")}
          title={t("confirmReject.title")}
          message={t("confirmReject.message")}
          confirmLabel={t("confirmReject.confirm")}
          cancelLabel={t("confirmReject.cancel")}
          color="failure"
          size={size}
          disabled={props.pending}
          onConfirm={() => props.onChange("rejected")}
        />
      ) : null}
    </>
  );
};
