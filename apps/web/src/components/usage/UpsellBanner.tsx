"use client";

import { Alert } from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { UsageLevel } from "@/lib/usage";

interface UpsellBannerProps {
  level: UsageLevel;
  percent: number;
  locale: string;
  showCta?: boolean;
  suppressOnUsage?: boolean;
}

type ActiveLevel = Exclude<UsageLevel, "ok">;

const COLOR: Record<ActiveLevel, "info" | "warning" | "failure"> = {
  notice: "info",
  upsell: "warning",
  blocked: "failure",
};

const TITLE_KEY: Record<ActiveLevel, string> = {
  notice: "noticeTitle",
  upsell: "upsellTitle",
  blocked: "blockedTitle",
};

const BODY_KEY: Record<ActiveLevel, string> = {
  notice: "noticeBody",
  upsell: "upsellBody",
  blocked: "blockedBody",
};

export const UpsellBanner: React.FC<UpsellBannerProps> = (props) => {
  const t = useTranslations("usage.upsell");
  const pathname = usePathname();
  const level = props.level;
  if (level === "ok") {
    return null;
  }
  // На самой странице /usage детальный баннер рисует страница — плашку из layout прячем.
  if (props.suppressOnUsage === true && pathname.endsWith("/usage")) {
    return null;
  }
  return (
    <Alert color={COLOR[level]}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm">
          <span className="font-medium">{t(TITLE_KEY[level], { percent: props.percent })}</span>{" "}
          <span>{t(BODY_KEY[level])}</span>
        </div>
        {props.showCta !== false ? (
          <Link
            href={`/${props.locale}/usage`}
            className="shrink-0 text-sm font-medium underline"
          >
            {t("cta")}
          </Link>
        ) : null}
      </div>
    </Alert>
  );
};
