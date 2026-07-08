"use client";

import { Sidebar, SidebarItem, SidebarItemGroup, SidebarItems } from "flowbite-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AdminIcon,
  BillingIcon,
  DashboardIcon,
  SettingsIcon,
  UsageIcon,
} from "@/components/ui/icons";

interface NavEntry {
  segment: string;
  key: "dashboard" | "settings" | "usage" | "billing" | "admin";
  icon: React.FC<React.SVGProps<SVGSVGElement>>;
}

interface AppSidebarProps {
  isPlatformAdmin: boolean;
}

const BASE_ENTRIES: NavEntry[] = [
  { segment: "dashboard", key: "dashboard", icon: DashboardIcon },
  { segment: "usage", key: "usage", icon: UsageIcon },
  { segment: "billing", key: "billing", icon: BillingIcon },
  { segment: "settings", key: "settings", icon: SettingsIcon },
];

const ADMIN_ENTRY: NavEntry = { segment: "admin", key: "admin", icon: AdminIcon };

export const AppSidebar: React.FC<AppSidebarProps> = (props) => {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const entries = props.isPlatformAdmin ? [...BASE_ENTRIES, ADMIN_ENTRY] : BASE_ENTRIES;

  const isActive = (segment: string): boolean =>
    pathname === `/${locale}/${segment}` || pathname.startsWith(`/${locale}/${segment}/`);

  return (
    <Sidebar
      aria-label={t("mainNav")}
      className="h-full border-r border-gray-200 dark:border-gray-700"
    >
      <SidebarItems>
        <SidebarItemGroup>
          {entries.map((x) => (
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
