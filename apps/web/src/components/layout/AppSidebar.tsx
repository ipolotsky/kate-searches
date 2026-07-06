"use client";

import { Sidebar, SidebarItem, SidebarItemGroup, SidebarItems } from "flowbite-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DashboardIcon, SettingsIcon } from "@/components/ui/icons";

interface NavEntry {
  segment: string;
  key: "dashboard" | "settings";
  icon: React.FC<React.SVGProps<SVGSVGElement>>;
}

const ENTRIES: NavEntry[] = [
  { segment: "dashboard", key: "dashboard", icon: DashboardIcon },
  { segment: "settings", key: "settings", icon: SettingsIcon },
];

export const AppSidebar: React.FC = () => {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();

  const isActive = (segment: string): boolean =>
    pathname === `/${locale}/${segment}` || pathname.startsWith(`/${locale}/${segment}/`);

  return (
    <Sidebar
      aria-label={t("mainNav")}
      className="h-full border-r border-gray-200 dark:border-gray-700"
    >
      <SidebarItems>
        <SidebarItemGroup>
          {ENTRIES.map((x) => (
            <SidebarItem
              key={x.segment}
              as={Link}
              href={`/${locale}/${x.segment}`}
              icon={x.icon}
              active={isActive(x.segment)}
            >
              {t(x.key)}
            </SidebarItem>
          ))}
        </SidebarItemGroup>
      </SidebarItems>
    </Sidebar>
  );
};
