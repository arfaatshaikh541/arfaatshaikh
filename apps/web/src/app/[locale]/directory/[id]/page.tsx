import { notFound } from "next/navigation";
import { DirectoryDetail } from "@/components/directory-detail";
import { asLocale } from "@/i18n/route-locale";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function DirectoryDetailPage({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  if (!UUID.test(id)) notFound();
  return <DirectoryDetail locale={asLocale(locale)} id={id} />;
}
