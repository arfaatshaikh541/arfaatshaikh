import { DirectoryBrowser } from "@/components/directory-browser";
import { asLocale } from "@/i18n/route-locale";

export default async function DirectoryPage({ params, searchParams }: { params: Promise<{ locale: string }>; searchParams: Promise<{ type?: string }> }) {
  const { locale } = await params;
  const { type } = await searchParams;
  return <DirectoryBrowser locale={asLocale(locale)} initialType={type} />;
}
