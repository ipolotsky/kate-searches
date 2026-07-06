"use client";

import { Dropdown, DropdownItem } from "flowbite-react";
import { useLocale } from "next-intl";
import { usePathname, useRouter } from "next/navigation";
import { routing } from "@/i18n/routing";

const LABELS: Record<string, string> = { en: "EN", ru: "RU" };

export const LocaleSwitcher: React.FC = () => {
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  const switchTo = (next: string): void => {
    if (next === locale) {
      return;
    }
    const segments = pathname.split("/");
    // segments[0] всегда "", segments[1] — текущая локаль в префиксе пути.
    if (routing.locales.includes(segments[1] as (typeof routing.locales)[number])) {
      segments[1] = next;
    } else {
      segments.splice(1, 0, next);
    }
    router.push(segments.join("/") || "/");
  };

  return (
    <Dropdown label={LABELS[locale] ?? locale.toUpperCase()} size="sm" color="light" inline>
      {routing.locales.map((x) => (
        <DropdownItem key={x} onClick={() => switchTo(x)}>
          {LABELS[x] ?? x.toUpperCase()}
        </DropdownItem>
      ))}
    </Dropdown>
  );
};
