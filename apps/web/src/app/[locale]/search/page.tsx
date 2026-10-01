import { asLocale } from "@/i18n/route-locale";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { GlobalSearch } from "@/components/global-search";
import { getMessages } from "@/i18n/messages";

export default async function SearchPage({ params }: { params: Promise<{ locale:string }> }) {
  const {locale:rawLocale }=await params;const locale=asLocale(rawLocale);
  const ar = locale === "ar";
  const t = getMessages(locale);
  return (
    <main className="world-page">
      <header className="topbar">
        <Brand locale={locale} />
        <WorldsNav locale={locale} />
        <LocaleSwitcher locale={locale} label={t.language} />
      </header>
      <header className="world-page-hero">
        <h1>{ar ? "البحث في عالم الإسلام" : "Search World of Islam"}</h1>
        <p>
          {ar
            ? "بحث موحَّد عبر كل المصادر المنشورة والموثقة، مع بيان نوع كل نتيجة ومصدرها."
            : "One search across every published, verified source. Each result shows its type and where it came from."}
        </p>
      </header>
      <GlobalSearch locale={locale} />
    </main>
  );
}
