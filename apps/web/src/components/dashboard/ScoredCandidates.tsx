"use client";

import { Button, Checkbox, Spinner } from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { generateDrafts } from "@/app/[locale]/(app)/_actions/pipeline";
import { PriorityBadge } from "@/components/ui/PriorityBadge";
import { ScoreBadge } from "@/components/ui/ScoreBadge";
import { useToast } from "@/components/ui/ToastProvider";
import type { CandidateView } from "@/lib/types";

interface ScoredCandidatesProps {
  candidates: CandidateView[];
  locale: string;
}

export const ScoredCandidates: React.FC<ScoredCandidatesProps> = (props) => {
  const t = useTranslations();
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const toggle = (id: string): void => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const allSelected = props.candidates.length > 0 && selected.size === props.candidates.length;

  const toggleAll = (): void => {
    setSelected(allSelected ? new Set() : new Set(props.candidates.map((x) => x.id)));
  };

  const generate = async (): Promise<void> => {
    if (selected.size === 0) {
      return;
    }
    setLoading(true);
    const result = await generateDrafts([...selected], props.locale);
    setLoading(false);
    if (result.ok) {
      toast.show(t("dashboard.candidates.queued"), "success");
      setSelected(new Set());
    } else if (result.code === "budgetExceeded") {
      toast.show(t("dashboard.candidates.budgetExceeded"), "error");
    } else if (result.code === "nothing") {
      toast.show(t("dashboard.candidates.nothing"), "info");
    } else {
      toast.show(t("dashboard.candidates.failed"), "error");
    }
  };

  if (props.candidates.length === 0) {
    return null;
  }

  return (
    <section className="mb-8 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t("dashboard.candidates.title")}
          </h2>
          <p className="text-sm text-gray-500">{t("dashboard.candidates.subtitle")}</p>
        </div>
        <Button
          color="blue"
          size="sm"
          disabled={selected.size === 0 || loading}
          onClick={generate}
        >
          {loading ? <Spinner size="sm" className="mr-2" /> : null}
          {t("dashboard.candidates.generate", { count: selected.size })}
        </Button>
      </div>

      <div className="mb-2 flex items-center gap-2 border-b border-gray-100 pb-2 dark:border-gray-700">
        <Checkbox
          id="candidates-all"
          checked={allSelected}
          onChange={toggleAll}
          aria-label={t("dashboard.candidates.selectAll")}
        />
        <label htmlFor="candidates-all" className="text-sm text-gray-500">
          {t("dashboard.candidates.selectAll")}
        </label>
      </div>

      <ul className="divide-y divide-gray-100 dark:divide-gray-700">
        {props.candidates.map((x) => (
          <li key={x.id} className="flex items-start gap-3 py-2">
            <Checkbox
              className="mt-1"
              checked={selected.has(x.id)}
              onChange={() => toggle(x.id)}
              aria-label={x.title}
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                {x.priority != null ? <PriorityBadge priority={x.priority} /> : null}
                {x.score != null ? <ScoreBadge score={x.score} /> : null}
              </div>
              <Link
                href={`/${props.locale}/articles/${x.id}`}
                className="block truncate text-sm font-medium text-gray-900 hover:underline dark:text-white"
              >
                {x.title.length > 0 ? x.title : x.url}
              </Link>
              {x.source != null ? (
                <span className="text-xs text-gray-400">{x.source.title ?? x.source.url}</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
};
