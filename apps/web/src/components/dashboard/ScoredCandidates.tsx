"use client";

import { Badge, Button, Checkbox, Spinner } from "flowbite-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";
import { generateDrafts } from "@/app/[locale]/(app)/_actions/pipeline";
import { PriorityBadge } from "@/components/ui/PriorityBadge";
import { ScoreBadge } from "@/components/ui/ScoreBadge";
import { useToast } from "@/components/ui/ToastProvider";
import { ChevronDownIcon } from "@/components/ui/icons";
import type { CandidateView } from "@/lib/types";

interface ScoredCandidatesProps {
  candidates: CandidateView[];
  locale: string;
}

export const ScoredCandidates: React.FC<ScoredCandidatesProps> = (props) => {
  const t = useTranslations();
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isPreviousOpen, setIsPreviousOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const recentCandidates = props.candidates.filter((x) => x.isNew);
  const previousCandidates = props.candidates.filter((x) => !x.isNew);
  const hasBoth = recentCandidates.length > 0 && previousCandidates.length > 0;

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

  const allRecentSelected =
    recentCandidates.length > 0 && recentCandidates.every((x) => selected.has(x.id));

  const allPreviousSelected =
    previousCandidates.length > 0 && previousCandidates.every((x) => selected.has(x.id));

  const toggleRecentAll = (): void => {
    setSelected((current) => {
      const next = new Set(current);
      if (allRecentSelected) {
        for (const item of recentCandidates) {
          next.delete(item.id);
        }
      } else {
        for (const item of recentCandidates) {
          next.add(item.id);
        }
      }
      return next;
    });
  };

  const togglePreviousAll = (): void => {
    setSelected((current) => {
      const next = new Set(current);
      if (allPreviousSelected) {
        for (const item of previousCandidates) {
          next.delete(item.id);
        }
      } else {
        for (const item of previousCandidates) {
          next.add(item.id);
        }
      }
      return next;
    });
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

  const renderCandidateList = (items: CandidateView[]) => (
    <ul className="divide-y divide-gray-100 dark:divide-gray-700">
      {items.map((x) => (
        <li key={x.id} className="flex items-start gap-3 py-2">
          <Checkbox
            id={`candidate-${x.id}`}
            className="mt-1"
            checked={selected.has(x.id)}
            onChange={() => toggle(x.id)}
            aria-label={x.title.length > 0 ? x.title : x.url}
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
  );

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

      {hasBoth ? (
        <>
          <div className="mb-4">
            <div className="mb-2 flex items-center justify-between border-b border-gray-100 pb-2 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                {t("dashboard.candidates.recentTitle")}
              </h3>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="candidates-recent-all"
                  checked={allRecentSelected}
                  onChange={toggleRecentAll}
                  aria-label={t("dashboard.candidates.selectAllRecent")}
                />
                <label
                  htmlFor="candidates-recent-all"
                  className="cursor-pointer text-sm text-gray-500 dark:text-gray-400"
                >
                  {t("dashboard.candidates.selectAllRecent")}
                </label>
              </div>
            </div>
            {renderCandidateList(recentCandidates)}
          </div>

          <div className="border-t border-gray-100 pt-3 dark:border-gray-700">
            <button
              type="button"
              onClick={() => setIsPreviousOpen((open) => !open)}
              aria-expanded={isPreviousOpen}
              aria-controls="previous-candidates-content"
              className="flex w-full items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-left text-sm font-medium text-gray-700 hover:bg-gray-100 dark:bg-gray-700/50 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              <div className="flex items-center gap-2">
                <span>{t("dashboard.candidates.previousTitle")}</span>
                <Badge color="gray">{previousCandidates.length}</Badge>
              </div>
              <ChevronDownIcon
                className={`h-4 w-4 text-gray-500 transition-transform duration-200 ${
                  isPreviousOpen ? "rotate-180" : ""
                }`}
              />
            </button>

            {isPreviousOpen && (
              <div id="previous-candidates-content" className="mt-3">
                <div className="mb-2 flex items-center justify-end gap-2 border-b border-gray-100 pb-2 dark:border-gray-700">
                  <Checkbox
                    id="candidates-previous-all"
                    checked={allPreviousSelected}
                    onChange={togglePreviousAll}
                    aria-label={t("dashboard.candidates.selectAllPrevious")}
                  />
                  <label
                    htmlFor="candidates-previous-all"
                    className="cursor-pointer text-sm text-gray-500 dark:text-gray-400"
                  >
                    {t("dashboard.candidates.selectAllPrevious")}
                  </label>
                </div>
                {renderCandidateList(previousCandidates)}
              </div>
            )}
          </div>
        </>
      ) : (
        <div>
          <div className="mb-2 flex items-center gap-2 border-b border-gray-100 pb-2 dark:border-gray-700">
            <Checkbox
              id="candidates-all"
              checked={recentCandidates.length > 0 ? allRecentSelected : allPreviousSelected}
              onChange={recentCandidates.length > 0 ? toggleRecentAll : togglePreviousAll}
              aria-label={t("dashboard.candidates.selectAll")}
            />
            <label
              htmlFor="candidates-all"
              className="cursor-pointer text-sm text-gray-500 dark:text-gray-400"
            >
              {t("dashboard.candidates.selectAll")}
            </label>
          </div>
          {renderCandidateList(recentCandidates.length > 0 ? recentCandidates : previousCandidates)}
        </div>
      )}
    </section>
  );
};
