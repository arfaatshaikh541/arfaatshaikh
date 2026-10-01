import { StatusOverview } from "@/components/status-overview";
import { asLocale } from "@/i18n/route-locale";

export default async function StatusPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  return <StatusOverview locale={asLocale(locale)} />;
}
