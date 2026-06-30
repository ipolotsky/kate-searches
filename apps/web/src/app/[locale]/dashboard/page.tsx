import { getTranslations, setRequestLocale } from "next-intl/server";
import { PostCard, type Post } from "@/components/PostCard";

// Заглушка данных. TODO(M4): тянуть из FastAPI/Supabase, скоупится по тенанту через RLS.
const MOCK_POSTS: Post[] = [
  {
    id: "1",
    title: "Salomon снова в центре gorpcore — что это значит для ресейла",
    sourceName: "Hypebeast",
    sourceUrl: "https://hypebeast.com/",
    score: 87,
    priority: "HOT",
    model: "gpt-5-mini",
    status: "new",
  },
  {
    id: "2",
    title: "Возвращение архивных кодов Margiela: разбор",
    sourceName: "Vogue Business",
    sourceUrl: "https://www.voguebusiness.com/",
    score: 72,
    priority: "WARM",
    model: "gpt-5-mini",
    status: "in_progress",
  },
];

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("dashboard");

  const fresh = MOCK_POSTS.filter((p) => p.status === "new");
  const inProgress = MOCK_POSTS.filter((p) => p.status === "in_progress");

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-1 text-2xl font-bold">{t("title")}</h1>
      <p className="mb-6 text-sm text-gray-500">{t("subtitle")}</p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">{t("sections.new")}</h2>
        {fresh.length === 0 ? (
          <p className="text-gray-500">{t("empty")}</p>
        ) : (
          <div className="grid gap-4">
            {fresh.map((p) => (
              <PostCard key={p.id} post={p} locale={locale} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">{t("sections.inProgress")}</h2>
        <div className="grid gap-4">
          {inProgress.map((p) => (
            <PostCard key={p.id} post={p} locale={locale} />
          ))}
        </div>
      </section>
    </main>
  );
}
