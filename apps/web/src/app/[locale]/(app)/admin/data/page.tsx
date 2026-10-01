import { AdminDataPanel } from "@/components/admin-data-panel";
import { asLocale } from "@/i18n/route-locale";

export default async function AdminDataPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  return <AdminDataPanel locale={asLocale(locale)} />;
}
