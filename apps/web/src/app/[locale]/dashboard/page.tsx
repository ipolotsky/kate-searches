import { getTranslations, setRequestLocale } from "next-intl/server";
import { redirect } from "next/navigation";
import { signOut } from "@/app/[locale]/auth/actions";
import { createClient } from "@/lib/supabase/server";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("dashboard");
  const tAuth = await getTranslations("auth");

  const supabase = await createClient();
  const userResult = await supabase.auth.getUser();
  const user = userResult.data.user;
  if (user == null) {
    redirect(`/${locale}/login`);
  }

  const profile = await supabase.from("users").select("tenant_id").eq("id", user.id).maybeSingle();
  let tenantName = "";
  if (profile.data?.tenant_id != null) {
    const tenant = await supabase
      .from("tenants")
      .select("name")
      .eq("id", profile.data.tenant_id)
      .maybeSingle();
    tenantName = tenant.data?.name ?? "";
  }

  const postsResult = await supabase.from("posts").select("id, title, status").order("created_at", {
    ascending: false,
  });
  const posts = postsResult.data ?? [];

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="mb-1 text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-gray-500">{t("subtitle")}</p>
        </div>
        <div className="text-right text-sm text-gray-500">
          <p>{t("signedInAs", { email: user.email ?? "" })}</p>
          {tenantName.length > 0 ? <p className="font-medium">{tenantName}</p> : null}
          <form action={signOut} className="mt-2">
            <input type="hidden" name="locale" value={locale} />
            <button type="submit" className="text-blue-600 hover:underline">
              {tAuth("signOut")}
            </button>
          </form>
        </div>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">{t("sections.new")}</h2>
        {posts.length === 0 ? (
          <p className="text-gray-500">{t("empty")}</p>
        ) : (
          <ul className="grid gap-2">
            {posts.map((x) => (
              <li key={x.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
                {x.title}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
