import { setRequestLocale } from "next-intl/server";
import { AppNavbar } from "@/components/layout/AppNavbar";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { ToastProvider } from "@/components/ui/ToastProvider";
import { getUserAndTenant } from "@/lib/auth/tenant";
import { createClient } from "@/lib/supabase/server";

export default async function AppLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  // Guard + единый доверенный tenant_id; редирект на login при отсутствии сессии/тенанта.
  const { email, tenantId } = await getUserAndTenant(locale);
  const supabase = await createClient();
  const tenant = await supabase.from("tenants").select("name").eq("id", tenantId).maybeSingle();
  const tenantName = tenant.data?.name ?? "";

  return (
    <ToastProvider>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <AppNavbar email={email} tenantName={tenantName} />
        <div className="mx-auto flex w-full max-w-7xl">
          <aside className="hidden w-60 shrink-0 border-gray-200 md:block">
            <AppSidebar />
          </aside>
          <main className="min-w-0 flex-1 px-4 py-6 sm:px-6">{children}</main>
        </div>
      </div>
    </ToastProvider>
  );
}
