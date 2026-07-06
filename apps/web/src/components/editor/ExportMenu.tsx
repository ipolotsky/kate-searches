"use client";

import { Dropdown, DropdownItem } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useToast } from "@/components/ui/ToastProvider";
import { copyAsText } from "@/lib/export/copyAsText";
import type { ExportablePost } from "@/lib/export/post";
import { toHtml } from "@/lib/export/toHtml";
import { toMarkdown } from "@/lib/export/toMarkdown";

interface ExportMenuProps {
  post: ExportablePost;
  fallbackName: string;
}

const slug = (value: string, fallback: string): string => {
  const normalized = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 60);
  return normalized.length > 0 ? normalized : fallback;
};

const download = (content: string, filename: string, mime: string): void => {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

export const ExportMenu: React.FC<ExportMenuProps> = (props) => {
  const t = useTranslations("export");
  const toast = useToast();
  const base = slug(props.post.title, props.fallbackName);

  const exportMarkdown = (): void => {
    download(toMarkdown(props.post), `${base}.md`, "text/markdown;charset=utf-8");
  };

  const exportHtml = (): void => {
    download(toHtml(props.post), `${base}.html`, "text/html;charset=utf-8");
  };

  const copy = async (): Promise<void> => {
    try {
      await copyAsText(props.post);
      toast.show(t("copied"), "success");
    } catch {
      toast.show(t("copyFailed"), "error");
    }
  };

  return (
    <Dropdown label={t("action")} color="light" size="sm">
      <DropdownItem onClick={exportMarkdown}>{t("markdown")}</DropdownItem>
      <DropdownItem onClick={exportHtml}>{t("html")}</DropdownItem>
      <DropdownItem onClick={copy}>{t("copy")}</DropdownItem>
    </Dropdown>
  );
};
