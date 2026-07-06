"use client";

import "@uiw/react-md-editor/markdown-editor.css";
import { Spinner } from "flowbite-react";
import { useTranslations } from "next-intl";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

// Извлечён из inline loading, чтобы иметь доступ к next-intl (fallback рендерится в провайдере).
const EditorLoading: React.FC = () => {
  const t = useTranslations("editor");
  return (
    <div className="flex h-64 items-center justify-center rounded-lg border border-gray-200 dark:border-gray-700">
      <Spinner aria-label={t("loadingEditor")} />
    </div>
  );
};

const MDEditor = dynamic(() => import("@uiw/react-md-editor"), {
  ssr: false,
  loading: () => <EditorLoading />,
});

interface MarkdownFieldProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  height?: number;
}

// data-color-mode берётся из фактического класса `dark` на <html> (его ставит ThemeModeScript
// и переключатель), а не из useThemeMode — так редактор всегда совпадает с темой, включая
// переключение на лету. MDEditor рендерится client-only (ssr:false).
export const MarkdownField: React.FC<MarkdownFieldProps> = (props) => {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const sync = (): void => setDark(root.classList.contains("dark"));
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return (
    <div data-color-mode={dark ? "dark" : "light"} onBlur={() => props.onBlur?.()}>
      <MDEditor
        value={props.value}
        onChange={(value) => props.onChange(value ?? "")}
        height={props.height ?? 460}
        preview="live"
      />
    </div>
  );
};
