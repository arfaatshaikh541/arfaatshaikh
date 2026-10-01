import { OfflineManager } from "@/components/offline-manager";
import { asLocale } from "@/i18n/route-locale";

export default async function OfflinePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  return <OfflineManager locale={asLocale(locale)} />;
}
