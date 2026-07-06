"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { updatePostStatus } from "@/app/[locale]/(app)/_actions/posts";
import { useToast } from "@/components/ui/ToastProvider";
import type { PostStatus, PostView } from "@/lib/types";
import { PostCard } from "./PostCard";
import { StatusSection } from "./StatusSection";

interface DraftsBoardProps {
  posts: PostView[];
  locale: string;
}

const SECTIONS: { status: PostStatus; defaultOpen: boolean }[] = [
  { status: "new", defaultOpen: true },
  { status: "in_progress", defaultOpen: false },
  { status: "published", defaultOpen: false },
  { status: "rejected", defaultOpen: false },
  { status: "archived", defaultOpen: false },
];

export const DraftsBoard: React.FC<DraftsBoardProps> = (props) => {
  const t = useTranslations();
  const toast = useToast();
  // Рендер идёт от props (revalidatePath/RSC обновляет доску); optimistic-статусы держим
  // в карте override поверх props — изолированно по посту, без клоббера соседних карточек.
  const [overrides, setOverrides] = useState<Record<string, PostStatus>>({});
  const [pending, setPending] = useState<Record<string, boolean>>({});

  const posts = props.posts.map((x) =>
    overrides[x.id] != null ? { ...x, status: overrides[x.id] } : x,
  );

  // Когда ревалидированные props догнали override (сервер подтвердил статус) — снимаем override,
  // чтобы дальше доской управляли props.
  useEffect(() => {
    setOverrides((current) => {
      const next: Record<string, PostStatus> = {};
      for (const [id, status] of Object.entries(current)) {
        const fromProps = props.posts.find((x) => x.id === id);
        if (fromProps != null && fromProps.status !== status) {
          next[id] = status;
        }
      }
      return next;
    });
  }, [props.posts]);

  const setOverride = (postId: string, status: PostStatus | null): void => {
    setOverrides((current) => {
      const next = { ...current };
      if (status == null) {
        delete next[postId];
      } else {
        next[postId] = status;
      }
      return next;
    });
  };

  const handleAction = useCallback(
    async (postId: string, next: PostStatus): Promise<void> => {
      setOverride(postId, next);
      setPending((current) => ({ ...current, [postId]: true }));

      const result = await updatePostStatus(postId, next, props.locale);

      setPending((current) => ({ ...current, [postId]: false }));
      if (result.ok) {
        toast.show(t("common.toasts.statusUpdated"), "success");
      } else {
        setOverride(postId, null);
        toast.show(t("common.toasts.statusFailed"), "error");
      }
    },
    [props.locale, t, toast],
  );

  if (posts.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-gray-500 dark:border-gray-700">
        {t("dashboard.empty")}
      </p>
    );
  }

  return (
    <div>
      {SECTIONS.map((section) => {
        const items = posts.filter((x) => x.status === section.status);
        if (items.length === 0) {
          return null;
        }
        return (
          <StatusSection
            key={section.status}
            title={t(`dashboard.statuses.${section.status}`)}
            count={items.length}
            defaultOpen={section.defaultOpen}
          >
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((x) => (
                <PostCard
                  key={x.id}
                  post={x}
                  locale={props.locale}
                  pending={pending[x.id] ?? false}
                  onAction={(next) => handleAction(x.id, next)}
                />
              ))}
            </div>
          </StatusSection>
        );
      })}
    </div>
  );
};
