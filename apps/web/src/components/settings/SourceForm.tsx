"use client";

import { Button, Checkbox, Label, Select, Spinner, TextInput } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { upsertSource } from "@/app/[locale]/(app)/_actions/settings";
import { testSource } from "@/app/[locale]/(app)/_actions/sources";
import { useToast } from "@/components/ui/ToastProvider";
import {
  type AdapterDescriptor,
  fieldKind,
  type JsonSchemaProperty,
  type SourceTestResponse,
} from "@/lib/sources/adapters";
import type { SourceView } from "@/lib/types";
import { SourceTestResult } from "./SourceTestResult";

interface SourceFormProps {
  adapters: AdapterDescriptor[];
  initial: SourceView | null;
  locale: string;
  onDone: () => void;
}

const humanize = (key: string): string =>
  key
    .split("_")
    .map((word) => (word.length > 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(" ");

const defaultConfig = (adapter: AdapterDescriptor | undefined): Record<string, unknown> => {
  const properties = adapter?.config_schema.properties ?? {};
  const result: Record<string, unknown> = {};
  for (const [key, property] of Object.entries(properties)) {
    if (property.default !== undefined && property.default !== null) {
      result[key] = property.default;
    }
  }
  return result;
};

export const SourceForm: React.FC<SourceFormProps> = (props) => {
  const t = useTranslations("sources");
  const toast = useToast();

  const firstType = props.adapters[0]?.type ?? "rss";
  const [type, setType] = useState(props.initial?.type ?? firstType);
  const [url, setUrl] = useState(props.initial?.url ?? "");
  const [title, setTitle] = useState(props.initial?.title ?? "");
  const [category, setCategory] = useState(props.initial?.category ?? "");
  const [priority, setPriority] = useState(props.initial?.priority ?? 3);
  const [enabled, setEnabled] = useState(props.initial?.enabled ?? true);
  const [config, setConfig] = useState<Record<string, unknown>>(
    props.initial?.config ?? defaultConfig(props.adapters.find((x) => x.type === firstType)),
  );

  const [testResult, setTestResult] = useState<SourceTestResponse | null>(null);
  const [bffError, setBffError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  const selected = props.adapters.find((x) => x.type === type);
  const properties = selected?.config_schema.properties ?? {};

  const changeType = (next: string): void => {
    setType(next);
    setConfig(defaultConfig(props.adapters.find((x) => x.type === next)));
    setTestResult(null);
    setBffError(null);
  };

  const setConfigValue = (key: string, value: unknown): void => {
    setConfig((current) => ({ ...current, [key]: value }));
  };

  const runTest = async (): Promise<void> => {
    if (url.trim().length === 0) {
      toast.show(t("urlRequired"), "error");
      return;
    }
    setTesting(true);
    setBffError(null);
    setTestResult(null);
    const result = await testSource({ type, url, config }, props.locale);
    setTesting(false);
    if (result.ok) {
      setTestResult(result.data as SourceTestResponse);
    } else {
      setBffError(result.code);
    }
  };

  const save = async (): Promise<void> => {
    if (url.trim().length === 0) {
      toast.show(t("urlRequired"), "error");
      return;
    }
    setSaving(true);
    const result = await upsertSource(
      { id: props.initial?.id ?? null, type, url, title, category, priority, config, enabled },
      props.locale,
    );
    setSaving(false);
    if (result.ok) {
      toast.show(t("saved"), "success");
      props.onDone();
    } else {
      toast.show(
        result.code === "trialSourcesLimit" ? t("trialSourcesLimit") : t("saveFailed"),
        "error",
      );
    }
  };

  const renderConfigField = (key: string, property: JsonSchemaProperty): React.ReactNode => {
    const kind = fieldKind(property);
    const label = property.title ?? humanize(key);
    const fieldId = `config-${key}`;

    if (kind === "boolean") {
      return (
        <label key={key} className="flex items-center gap-2 text-sm">
          <Checkbox
            id={fieldId}
            checked={Boolean(config[key])}
            onChange={(event) => setConfigValue(key, event.target.checked)}
          />
          {label}
        </label>
      );
    }

    if (kind === "number") {
      return (
        <div key={key}>
          <Label htmlFor={fieldId} className="mb-1 block">
            {label}
          </Label>
          <TextInput
            id={fieldId}
            type="number"
            value={typeof config[key] === "number" ? (config[key] as number) : ""}
            onChange={(event) => setConfigValue(key, Number(event.target.value))}
          />
        </div>
      );
    }

    if (kind === "select") {
      return (
        <div key={key}>
          <Label htmlFor={fieldId} className="mb-1 block">
            {label}
          </Label>
          <Select
            id={fieldId}
            value={String(config[key] ?? "")}
            onChange={(event) => setConfigValue(key, event.target.value)}
          >
            {(property.enum ?? []).map((option) => (
              <option key={String(option)} value={String(option)}>
                {String(option)}
              </option>
            ))}
          </Select>
        </div>
      );
    }

    return (
      <div key={key}>
        <Label htmlFor={fieldId} className="mb-1 block">
          {label}
        </Label>
        <TextInput
          id={fieldId}
          value={typeof config[key] === "string" ? (config[key] as string) : ""}
          onChange={(event) => setConfigValue(key, event.target.value)}
        />
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
        {props.initial != null ? t("edit") : t("addNew")}
      </h3>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="source-type" className="mb-1 block">
            {t("type")}
          </Label>
          <Select
            id="source-type"
            value={type}
            onChange={(event) => changeType(event.target.value)}
          >
            {props.adapters.map((x) => (
              <option key={x.type} value={x.type}>
                {x.type}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="source-priority" className="mb-1 block">
            {t("priority")}
          </Label>
          <TextInput
            id="source-priority"
            type="number"
            min={1}
            max={5}
            value={priority}
            onChange={(event) => setPriority(Number(event.target.value))}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="source-url" className="mb-1 block">
          {t("url")}
        </Label>
        <TextInput
          id="source-url"
          type="url"
          required
          value={url}
          onChange={(event) => setUrl(event.target.value)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="source-title" className="mb-1 block">
            {t("titleField")}
          </Label>
          <TextInput
            id="source-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="source-category" className="mb-1 block">
            {t("category")}
          </Label>
          <TextInput
            id="source-category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          />
        </div>
      </div>

      {Object.keys(properties).length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {Object.entries(properties).map(([key, property]) => renderConfigField(key, property))}
        </div>
      ) : null}

      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
        {t("enabled")}
      </label>

      {bffError != null ? (
        <p className="text-sm text-red-500">{t(`testErrors.${bffError}`)}</p>
      ) : null}
      {testResult != null ? <SourceTestResult response={testResult} /> : null}

      <div className="flex flex-wrap gap-2">
        <Button color="light" onClick={runTest} disabled={testing}>
          {testing ? <Spinner size="sm" className="mr-2" /> : null}
          {t("test")}
        </Button>
        <Button color="blue" onClick={save} disabled={saving}>
          {t("save")}
        </Button>
        <Button color="light" onClick={props.onDone} disabled={saving}>
          {t("cancel")}
        </Button>
      </div>
    </div>
  );
};
