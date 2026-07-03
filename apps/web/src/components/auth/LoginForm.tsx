"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { login } from "@/app/[locale]/auth/actions";

export const LoginForm: React.FC = () => {
  const t = useTranslations("auth.login");
  const locale = useLocale();

  return (
    <form action={login} className="flex flex-col gap-4">
      <input type="hidden" name="locale" value={locale} />
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">{t("email")}</span>
        <input
          type="email"
          name="email"
          required
          autoComplete="email"
          className="rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-700 dark:bg-gray-800"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">{t("password")}</span>
        <input
          type="password"
          name="password"
          required
          autoComplete="current-password"
          className="rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-700 dark:bg-gray-800"
        />
      </label>
      <button
        type="submit"
        className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
      >
        {t("submit")}
      </button>
      <p className="text-sm text-gray-500">
        {t("noAccount")}{" "}
        <Link href={`/${locale}/register`} className="text-blue-600 hover:underline">
          {t("registerLink")}
        </Link>
      </p>
    </form>
  );
};
