import { getTranslations, setRequestLocale } from "next-intl/server";
import { getAdapters } from "@/app/[locale]/(app)/_actions/sources";
import { type BrandProfileInitial, BrandProfileForm } from "@/components/settings/BrandProfileForm";
import { SourcesSection } from "@/components/settings/SourcesSection";
import { routing } from "@/i18n/routing";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { createClient } from "@/lib/supabase/server";
import { type SourceView, parseJsonLd, parseVoiceExamples } from "@/lib/types";

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("settings");
  await getUserAndTenant(locale);
  const supabase = await createClient();

  const profileResult = await supabase.from("brand_profiles").select("*").maybeSingle();
  if (profileResult.error != null) {
    throw new Error(profileResult.error.message);
  }
  const profile = profileResult.data;
  const initial: BrandProfileInitial = {
    companyDescription: profile?.company_description ?? "",
    audienceDescription: profile?.audience_description ?? "",
    filterCriteria: profile?.filter_criteria ?? "",
    voiceConfig: parseJsonLd(profile?.voice_config) ?? {},
    voiceExamples: parseVoiceExamples(profile?.voice_examples),
    scoreThreshold: profile?.score_threshold ?? 60,
    locales: profile?.locales ?? [routing.defaultLocale],
  };

  const sourcesResult = await supabase
    .from("sources")
    .select("*")
    .order("created_at", { ascending: true });
  if (sourcesResult.error != null) {
    throw new Error(sourcesResult.error.message);
  }
  const sources: SourceView[] = (sourcesResult.data ?? []).map((row) => ({
    id: row.id,
    type: row.type,
    url: row.url,
    title: row.title,
    category: row.category,
    priority: row.priority,
    config: parseJsonLd(row.config) ?? {},
    enabled: row.enabled,
    lastStatus: row.last_status,
    lastError: row.last_error,
    lastRunAt: row.last_run_at,
  }));

  const adapters = await getAdapters(locale);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{t("title")}</h1>
        <p className="text-sm text-gray-500">{t("subtitle")}</p>
      </div>

      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          {t("brand.title")}
        </h2>
        <BrandProfileForm initial={initial} locale={locale} />
      </section>

      <hr className="border-gray-200 dark:border-gray-700" />

      <SourcesSection sources={sources} adapters={adapters} locale={locale} />
    </div>
  );
}
