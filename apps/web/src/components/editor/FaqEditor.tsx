"use client";

import { Button, Label, Textarea, TextInput } from "flowbite-react";
import { useTranslations } from "next-intl";
import { PlusIcon, TrashIcon } from "@/components/ui/icons";
import type { FaqItem } from "@/lib/types";

interface FaqEditorProps {
  value: FaqItem[];
  onChange: (value: FaqItem[]) => void;
}

export const FaqEditor: React.FC<FaqEditorProps> = (props) => {
  const t = useTranslations("editor.faq");

  const update = (index: number, patch: Partial<FaqItem>): void => {
    props.onChange(props.value.map((x, i) => (i === index ? { ...x, ...patch } : x)));
  };

  const remove = (index: number): void => {
    props.onChange(props.value.filter((_, i) => i !== index));
  };

  const add = (): void => {
    props.onChange([...props.value, { question: "", answer: "" }]);
  };

  return (
    <div className="flex flex-col gap-4">
      {props.value.length === 0 ? (
        <p className="text-sm text-gray-500">{t("empty")}</p>
      ) : null}

      {props.value.map((item, index) => (
        // eslint-disable-next-line react/no-array-index-key
        <div key={index} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
          <div className="mb-2 flex items-center justify-between">
            <Label htmlFor={`faq-q-${index}`}>{t("question", { number: index + 1 })}</Label>
            <Button
              color="light"
              size="xs"
              aria-label={t("remove", { number: index + 1 })}
              onClick={() => remove(index)}
            >
              <TrashIcon className="h-4 w-4" />
            </Button>
          </div>
          <TextInput
            id={`faq-q-${index}`}
            value={item.question}
            onChange={(event) => update(index, { question: event.target.value })}
            className="mb-2"
          />
          <Label htmlFor={`faq-a-${index}`} className="mb-1 block">
            {t("answer")}
          </Label>
          <Textarea
            id={`faq-a-${index}`}
            rows={3}
            value={item.answer}
            onChange={(event) => update(index, { answer: event.target.value })}
          />
        </div>
      ))}

      <div>
        <Button color="light" size="sm" onClick={add}>
          <PlusIcon className="mr-2 h-4 w-4" />
          {t("add")}
        </Button>
      </div>
    </div>
  );
};
