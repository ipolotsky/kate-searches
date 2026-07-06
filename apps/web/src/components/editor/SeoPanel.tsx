"use client";

import { Badge } from "flowbite-react";
import { useTranslations } from "next-intl";
import type { PostSeo } from "@/lib/types";

interface SeoPanelProps {
  seo: PostSeo;
  suggestedTitles: string[];
}

interface FieldProps {
  label: string;
  children: React.ReactNode;
}

const Field: React.FC<FieldProps> = (props) => (
  <div>
    <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
      {props.label}
    </h4>
    {props.children}
  </div>
);

export const SeoPanel: React.FC<SeoPanelProps> = (props) => {
  const t = useTranslations("editor.seo");
  const seo = props.seo;
  const keywords = seo.keywords ?? [];
  const entities = seo.entities ?? [];

  return (
    <div className="flex flex-col gap-5">
      <p className="text-sm text-gray-500">{t("hint")}</p>

      {seo.meta_description != null && seo.meta_description.length > 0 ? (
        <Field label={t("metaDescription")}>
          <p className="text-sm text-gray-700 dark:text-gray-300">{seo.meta_description}</p>
        </Field>
      ) : null}

      {seo.brand_tie_in != null && seo.brand_tie_in.length > 0 ? (
        <Field label={t("brandTieIn")}>
          <p className="text-sm text-gray-700 dark:text-gray-300">{seo.brand_tie_in}</p>
        </Field>
      ) : null}

      {keywords.length > 0 ? (
        <Field label={t("keywords")}>
          <div className="flex flex-wrap gap-1.5">
            {keywords.map((x) => (
              <Badge key={x} color="gray">
                {x}
              </Badge>
            ))}
          </div>
        </Field>
      ) : null}

      {entities.length > 0 ? (
        <Field label={t("entities")}>
          <div className="flex flex-wrap gap-1.5">
            {entities.map((x) => (
              <Badge key={x} color="info">
                {x}
              </Badge>
            ))}
          </div>
        </Field>
      ) : null}

      {seo.seo_instructions != null && seo.seo_instructions.length > 0 ? (
        <Field label={t("instructions")}>
          <p className="whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-300">
            {seo.seo_instructions}
          </p>
        </Field>
      ) : null}

      {props.suggestedTitles.length > 0 ? (
        <Field label={t("suggestedTitles")}>
          <ul className="list-inside list-disc text-sm text-gray-700 dark:text-gray-300">
            {props.suggestedTitles.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </Field>
      ) : null}
    </div>
  );
};
