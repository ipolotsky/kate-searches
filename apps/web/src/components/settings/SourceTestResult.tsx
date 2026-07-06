"use client";

import { Alert, Badge } from "flowbite-react";
import { useTranslations } from "next-intl";
import type { SourceTestResponse } from "@/lib/sources/adapters";

interface SourceTestResultProps {
  response: SourceTestResponse;
}

export const SourceTestResult: React.FC<SourceTestResultProps> = (props) => {
  const t = useTranslations("sourceTest");
  const response = props.response;

  if (!response.ok) {
    const code = response.error ?? "fetch_error";
    return (
      <Alert color="failure">
        <span className="font-medium">{t(`errors.${code}`)}</span>
        {response.detail != null ? (
          <span className="ml-1 text-sm opacity-80">{response.detail}</span>
        ) : null}
      </Alert>
    );
  }

  const sample = response.sample ?? [];
  const warnings = response.warnings ?? [];

  return (
    <div className="flex flex-col gap-3">
      {response.error != null ? <Alert color="warning">{t(`errors.${response.error}`)}</Alert> : null}

      {warnings.length > 0 ? (
        <Alert color="warning">
          <div className="flex flex-wrap gap-1.5">
            {warnings.map((x) => (
              <Badge key={x} color="warning">
                {x}
              </Badge>
            ))}
          </div>
        </Alert>
      ) : null}

      <div>
        <h4 className="mb-2 text-sm font-semibold text-gray-900 dark:text-white">
          {t("sample", { count: sample.length })}
        </h4>
        {sample.length === 0 ? (
          <p className="text-sm text-gray-500">{t("noSample")}</p>
        ) : (
          <ul className="divide-y divide-gray-100 dark:divide-gray-700">
            {sample.map((x) => (
              <li key={x.url} className="py-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge color={x.is_novel ? "success" : "gray"}>
                    {x.is_novel ? t("novel") : t("seen")}
                  </Badge>
                  <Badge color={x.has_body ? "info" : "gray"}>
                    {x.has_body ? t("hasBody") : t("noBodyFlag")}
                  </Badge>
                  {x.language != null ? <span className="text-xs text-gray-400">{x.language}</span> : null}
                </div>
                <a
                  href={x.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block truncate text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
                >
                  {x.title != null && x.title.length > 0 ? x.title : x.url}
                </a>
                {x.body_preview.length > 0 ? (
                  <p className="line-clamp-2 text-xs text-gray-500">{x.body_preview}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
