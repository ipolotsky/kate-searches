"use client";

import { Badge, Textarea } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

interface JsonLdPreviewProps {
  value: Record<string, unknown> | null;
  onChange: (value: Record<string, unknown> | null) => void;
}

const stringify = (value: Record<string, unknown> | null): string =>
  value != null ? JSON.stringify(value, null, 2) : "";

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value != null && !Array.isArray(value);

export const JsonLdPreview: React.FC<JsonLdPreviewProps> = (props) => {
  const t = useTranslations("editor.jsonLd");
  const [text, setText] = useState<string>(stringify(props.value));
  const [valid, setValid] = useState(true);
  const baseId = useId();
  const labelId = `${baseId}-label`;
  const statusId = `${baseId}-status`;
  const hintId = `${baseId}-hint`;

  const handleChange = (next: string): void => {
    setText(next);
    if (next.trim().length === 0) {
      setValid(true);
      props.onChange(null);
      return;
    }
    try {
      const parsed: unknown = JSON.parse(next);
      if (isPlainObject(parsed)) {
        setValid(true);
        props.onChange(parsed);
      } else {
        setValid(false);
      }
    } catch {
      setValid(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h4 id={labelId} className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          {t("title")}
        </h4>
        <Badge id={statusId} role="status" aria-live="polite" color={valid ? "success" : "failure"}>
          {valid ? t("valid") : t("invalid")}
        </Badge>
      </div>
      <Textarea
        rows={12}
        value={text}
        onChange={(event) => handleChange(event.target.value)}
        className="font-mono text-xs"
        aria-invalid={!valid}
        aria-labelledby={labelId}
        aria-describedby={`${statusId} ${hintId}`}
      />
      <p id={hintId} className="text-xs text-gray-400">
        {t("hint")}
      </p>
    </div>
  );
};
