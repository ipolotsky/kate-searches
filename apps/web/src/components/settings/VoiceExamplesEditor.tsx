"use client";

import { Button, Label, Textarea, TextInput } from "flowbite-react";
import { useTranslations } from "next-intl";
import { PlusIcon, TrashIcon } from "@/components/ui/icons";
import type { VoiceExample } from "@/lib/types";

interface VoiceExamplesEditorProps {
  value: VoiceExample[];
  onChange: (value: VoiceExample[]) => void;
}

export const VoiceExamplesEditor: React.FC<VoiceExamplesEditorProps> = (props) => {
  const t = useTranslations("settings.voiceExamples");

  const update = (index: number, patch: Partial<VoiceExample>): void => {
    props.onChange(props.value.map((x, i) => (i === index ? { ...x, ...patch } : x)));
  };

  const remove = (index: number): void => {
    props.onChange(props.value.filter((_, i) => i !== index));
  };

  const add = (): void => {
    props.onChange([...props.value, { post_text: "", source_url: "", why: "" }]);
  };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{t("title")}</h3>
        <p className="text-sm text-gray-500">{t("hint")}</p>
      </div>

      {props.value.map((item, index) => (
        // eslint-disable-next-line react/no-array-index-key
        <div key={index} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium">{t("item", { number: index + 1 })}</span>
            <Button
              color="light"
              size="xs"
              aria-label={t("remove", { number: index + 1 })}
              onClick={() => remove(index)}
            >
              <TrashIcon className="h-4 w-4" />
            </Button>
          </div>
          <Label htmlFor={`voice-text-${index}`} className="mb-1 block">
            {t("postText")}
          </Label>
          <Textarea
            id={`voice-text-${index}`}
            rows={4}
            value={item.post_text}
            onChange={(event) => update(index, { post_text: event.target.value })}
            className="mb-2"
          />
          <Label htmlFor={`voice-url-${index}`} className="mb-1 block">
            {t("sourceUrl")}
          </Label>
          <TextInput
            id={`voice-url-${index}`}
            type="url"
            value={item.source_url}
            onChange={(event) => update(index, { source_url: event.target.value })}
            className="mb-2"
          />
          <Label htmlFor={`voice-why-${index}`} className="mb-1 block">
            {t("why")}
          </Label>
          <Textarea
            id={`voice-why-${index}`}
            rows={2}
            value={item.why}
            onChange={(event) => update(index, { why: event.target.value })}
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
