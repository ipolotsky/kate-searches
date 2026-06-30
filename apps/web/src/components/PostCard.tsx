import { useTranslations } from "next-intl";

export type Post = {
  id: string;
  title: string;
  sourceName: string;
  sourceUrl: string;
  score: number;
  priority: "HOT" | "WARM" | "COLD" | "DROP";
  model: string;
  status: "new" | "in_progress" | "published" | "rejected" | "archived";
};

const PRIORITY_STYLES: Record<Post["priority"], string> = {
  HOT: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  WARM: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  COLD: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  DROP: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200",
};

export function PostCard({ post, locale }: { post: Post; locale: string }) {
  const t = useTranslations("post");

  return (
    <article className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-2 flex items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-xs font-medium ${PRIORITY_STYLES[post.priority]}`}>
          {post.priority}
        </span>
        <span className="text-xs text-gray-500">
          {t("score")}: {post.score}
        </span>
        <span className="text-xs text-gray-400">· {post.model}</span>
      </div>

      <h3 className="mb-1 font-semibold">{post.title}</h3>

      <a
        href={post.sourceUrl}
        target="_blank"
        rel="noreferrer"
        className="text-sm text-blue-600 hover:underline dark:text-blue-400"
      >
        {t("source")}: {post.sourceName}
      </a>

      <div className="mt-3 flex gap-2">
        <a
          href={`/${locale}/posts/${post.id}`}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          {t("actions.edit")}
        </a>
        <button
          type="button"
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          {t("actions.reject")}
        </button>
      </div>
    </article>
  );
}
