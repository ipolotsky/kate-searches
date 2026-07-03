"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { register } from "@/app/[locale]/auth/actions";

export const RegisterForm: React.FC = () => {
  const t = useTranslations("auth.register");
  const locale = useLocale();

  return (
    <form action={register} className="flex flex-col gap-4">
      <input type="hidden" name="locale" value={locale} />
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">{t("company")}</span>
        <input
          type="text"
          name="company"
          required
          className="rounded-lg border border-gray-300 px-3 py-2 dark:border-gray-700 dark:bg-gray-800"
        />
      </label>
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
          minLength={8}
          autoComplete="new-password"
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
        {t("haveAccount")}{" "}
        <Link href={`/${locale}/login`} className="text-blue-600 hover:underline">
          {t("loginLink")}
        </Link>
      </p>
    </form>
  );
};
