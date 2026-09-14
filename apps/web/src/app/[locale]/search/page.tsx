import type { Locale } from "@world-of-islam/shared-types";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { GlobalSearch } from "@/components/global-search";
import { getMessages } from "@/i18n/messages";

export default async function SearchPage({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
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
            ? "بحث حقيقي عبر النصوص المعتمدة والمنشورة فقط - القرآن والحديث والتفسير. لا نتائج مُختلقة أو مُقترحة بالذكاء الاصطناعي هنا."
            : "Real search across approved, published text only — Qur'an, Hadith, and Tafsir. No AI-generated or fabricated results here."}
        </p>
      </header>
      <GlobalSearch locale={locale} />
    </main>
  );
}
