import { asLocale } from "@/i18n/route-locale";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { TopicsBrowser } from "@/components/topics-browser";
import { getMessages } from "@/i18n/messages";

export default async function TopicsPage({ params }: { params: Promise<{ locale:string }> }) {
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
        <h1>{ar ? "خريطة المعرفة" : "Knowledge topics"}</h1>
        <p>
          {ar
            ? "روابط بين آيات القرآن والأحاديث والتفسير والمواضيع ذات الصلة."
            : "Published links between Qur'an ayat, Hadith narrations, Tafsir entries, and related topics."}
        </p>
      </header>
      <TopicsBrowser locale={locale} />
    </main>
  );
}
