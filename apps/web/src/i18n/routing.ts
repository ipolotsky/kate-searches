import { defineRouting } from "next-intl/routing";

// i18n с первого дня: ru + en, расширяемо новыми локалями.
export const routing = defineRouting({
  locales: ["en", "ru"],
  defaultLocale: "en",
});

export type Locale = (typeof routing.locales)[number];
