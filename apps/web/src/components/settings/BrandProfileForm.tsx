"use client";

import { Button, Checkbox, Label, Textarea, TextInput } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { upsertBrandProfile } from "@/app/[locale]/(app)/_actions/settings";
import { useToast } from "@/components/ui/ToastProvider";
import { routing } from "@/i18n/routing";
import type { VoiceExample } from "@/lib/types";
import { VoiceExamplesEditor } from "./VoiceExamplesEditor";

export interface BrandProfileInitial {
  companyDescription: string;
  audienceDescription: string;
  filterCriteria: string;
  voiceConfig: Record<string, unknown>;
  voiceExamples: VoiceExample[];
  scoreThreshold: number;
  locales: string[];
}

interface BrandProfileFormProps {
  initial: BrandProfileInitial;
  locale: string;
}

const toneOf = (voiceConfig: Record<string, unknown>): string =>
  typeof voiceConfig.tone === "string" ? voiceConfig.tone : "";

export const BrandProfileForm: React.FC<BrandProfileFormProps> = (props) => {
  const t = useTranslations("settings.brand");
  const toast = useToast();

  const [companyDescription, setCompanyDescription] = useState(props.initial.companyDescription);
  const [audienceDescription, setAudienceDescription] = useState(
    props.initial.audienceDescription,
  );
  const [filterCriteria, setFilterCriteria] = useState(props.initial.filterCriteria);
  const [tone, setTone] = useState(toneOf(props.initial.voiceConfig));
  const [scoreThreshold, setScoreThreshold] = useState(props.initial.scoreThreshold);
  const [locales, setLocales] = useState<string[]>(props.initial.locales);
  const [voiceExamples, setVoiceExamples] = useState<VoiceExample[]>(props.initial.voiceExamples);
  const [loading, setLoading] = useState(false);

  const toggleLocale = (value: string): void => {
    setLocales((current) =>
      current.includes(value) ? current.filter((x) => x !== value) : [...current, value],
    );
  };

  const submit = async (): Promise<void> => {
    setLoading(true);
    const result = await upsertBrandProfile(
      {
        companyDescription,
        audienceDescription,
        filterCriteria,
        voiceConfig: { ...props.initial.voiceConfig, tone },
        voiceExamples,
        scoreThreshold,
        locales: locales.length > 0 ? locales : [routing.defaultLocale],
      },
      props.locale,
    );
    setLoading(false);
    toast.show(result.ok ? t("saved") : t("failed"), result.ok ? "success" : "error");
  };

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Label htmlFor="company-description" className="mb-1 block">
          {t("company")}
        </Label>
        <Textarea
          id="company-description"
          rows={3}
          value={companyDescription}
          onChange={(event) => setCompanyDescription(event.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="audience-description" className="mb-1 block">
          {t("audience")}
        </Label>
        <Textarea
          id="audience-description"
          rows={3}
          value={audienceDescription}
          onChange={(event) => setAudienceDescription(event.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="filter-criteria" className="mb-1 block">
          {t("filter")}
        </Label>
        <Textarea
          id="filter-criteria"
          rows={3}
          value={filterCriteria}
          onChange={(event) => setFilterCriteria(event.target.value)}
        />
        <p className="mt-1 text-xs text-gray-400">{t("filterHint")}</p>
      </div>

      <div>
        <Label htmlFor="voice-tone" className="mb-1 block">
          {t("tone")}
        </Label>
        <Textarea
          id="voice-tone"
          rows={2}
          value={tone}
          onChange={(event) => setTone(event.target.value)}
        />
      </div>

      <div className="max-w-xs">
        <Label htmlFor="score-threshold" className="mb-1 block">
          {t("threshold")}
        </Label>
        <TextInput
          id="score-threshold"
          type="number"
          min={0}
          max={100}
          value={scoreThreshold}
          onChange={(event) => setScoreThreshold(Number(event.target.value))}
        />
        <p className="mt-1 text-xs text-gray-400">{t("thresholdHint")}</p>
      </div>

      <fieldset>
        <legend className="mb-1 text-sm font-medium">{t("locales")}</legend>
        <div className="flex gap-4">
          {routing.locales.map((x) => (
            <label key={x} className="flex items-center gap-2 text-sm">
              <Checkbox checked={locales.includes(x)} onChange={() => toggleLocale(x)} />
              {x.toUpperCase()}
            </label>
          ))}
        </div>
      </fieldset>

      <VoiceExamplesEditor value={voiceExamples} onChange={setVoiceExamples} />

      <div>
        <Button color="blue" onClick={submit} disabled={loading}>
          {t("save")}
        </Button>
      </div>
    </div>
  );
};
