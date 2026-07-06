"use client";

import {
  DarkThemeToggle,
  Dropdown,
  DropdownDivider,
  DropdownHeader,
  DropdownItem,
  Navbar,
  NavbarBrand,
} from "flowbite-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { signOut } from "@/app/[locale]/auth/actions";
import { LocaleSwitcher } from "./LocaleSwitcher";

interface AppNavbarProps {
  email: string;
  tenantName: string;
}

export const AppNavbar: React.FC<AppNavbarProps> = (props) => {
  const t = useTranslations();
  const locale = useLocale();

  const handleSignOut = (): void => {
    const formData = new FormData();
    formData.set("locale", locale);
    void signOut(formData);
  };

  return (
    <Navbar fluid className="border-b border-gray-200 dark:border-gray-700">
      <NavbarBrand as={Link} href={`/${locale}/dashboard`}>
        <span className="self-center whitespace-nowrap text-xl font-semibold dark:text-white">
          {t("app.name")}
        </span>
      </NavbarBrand>
      <div className="flex items-center gap-2">
        <LocaleSwitcher />
        <DarkThemeToggle />
        <Dropdown
          arrowIcon={false}
          inline
          label={
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 text-sm font-semibold text-white">
              {(props.email[0] ?? "?").toUpperCase()}
            </span>
          }
        >
          <DropdownHeader>
            <span className="block text-sm font-medium">{props.tenantName}</span>
            <span className="block truncate text-sm text-gray-500">{props.email}</span>
          </DropdownHeader>
          <DropdownItem as={Link} href={`/${locale}/settings`}>
            {t("nav.settings")}
          </DropdownItem>
          <DropdownDivider />
          <DropdownItem onClick={handleSignOut}>{t("auth.signOut")}</DropdownItem>
        </Dropdown>
      </div>
    </Navbar>
  );
};
