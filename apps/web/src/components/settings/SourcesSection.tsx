"use client";

import { Button } from "flowbite-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { deleteSource } from "@/app/[locale]/(app)/_actions/settings";
import { PlusIcon } from "@/components/ui/icons";
import { useToast } from "@/components/ui/ToastProvider";
import type { AdapterDescriptor } from "@/lib/sources/adapters";
import type { SourceView } from "@/lib/types";
import { SourceForm } from "./SourceForm";
import { SourceRow } from "./SourceRow";

interface SourcesSectionProps {
  sources: SourceView[];
  adapters: AdapterDescriptor[];
  locale: string;
}

export const SourcesSection: React.FC<SourcesSectionProps> = (props) => {
  const t = useTranslations("sources");
  const toast = useToast();
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const closeAndRefresh = (): void => {
    setAdding(false);
    setEditingId(null);
    router.refresh();
  };

  const handleDelete = async (id: string): Promise<void> => {
    if (deletingId != null) {
      return;
    }
    setDeletingId(id);
    try {
      const result = await deleteSource(id, props.locale);
      if (result.ok) {
        toast.show(t("deleted"), "success");
        router.refresh();
      } else {
        toast.show(t("deleteFailed"), "error");
      }
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{t("title")}</h2>
          <p className="text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        {!adding && editingId == null ? (
          <Button color="blue" size="sm" onClick={() => setAdding(true)}>
            <PlusIcon className="mr-2 h-4 w-4" />
            {t("add")}
          </Button>
        ) : null}
      </div>

      {adding ? (
        <SourceForm
          adapters={props.adapters}
          initial={null}
          locale={props.locale}
          onDone={closeAndRefresh}
        />
      ) : null}

      {props.sources.length === 0 && !adding ? (
        <p className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700">
          {t("empty")}
        </p>
      ) : null}

      <div className="flex flex-col gap-3">
        {props.sources.map((source) =>
          editingId === source.id ? (
            <SourceForm
              key={source.id}
              adapters={props.adapters}
              initial={source}
              locale={props.locale}
              onDone={closeAndRefresh}
            />
          ) : (
            <SourceRow
              key={source.id}
              source={source}
              deleting={deletingId === source.id}
              onEdit={() => setEditingId(source.id)}
              onDelete={() => handleDelete(source.id)}
            />
          ),
        )}
      </div>
    </div>
  );
};
