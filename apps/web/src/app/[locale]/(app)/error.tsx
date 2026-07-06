"use client";

import { Button } from "flowbite-react";
import { useTranslations } from "next-intl";

// Граница ошибок для (app): показывает явное состояние ошибки с ретраем вместо
// пустого экрана, если RSC-запрос к БД упал (не путаем ошибку с «нет данных»).
export default function AppError({ reset }: { error: Error; reset: () => void }) {
  const t = useTranslations("common.error");

  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white">{t("title")}</h2>
      <p className="text-sm text-gray-500">{t("description")}</p>
      <Button color="blue" onClick={reset}>
        {t("retry")}
      </Button>
    </div>
  );
}
