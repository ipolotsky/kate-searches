import { setRequestLocale } from "next-intl/server";
import { assertPlatformAdmin } from "@/lib/auth/platform";

export default async function AdminLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  // Гейт платформенного админа: не-админа отдаём в 404 (раздел не раскрываем).
  await assertPlatformAdmin(locale);
  return <>{children}</>;
}
