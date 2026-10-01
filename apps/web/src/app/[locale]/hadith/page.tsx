import { asLocale } from "@/i18n/route-locale";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { HadithBrowser } from "@/components/hadith-browser";
import { LocaleSwitcher } from "@/components/locale-switcher";

export default async function HadithIndexPage({ params }: { params: Promise<{ locale:string }> }) {
  const {locale:rawLocale }=await params;const locale=asLocale(rawLocale);
  const ar = locale === "ar";
  return (
    <main className="quran-landing">
      <header className="topbar"><Brand locale={locale} /><LocaleSwitcher locale={locale} label={ar ? "اللغة" : "Language"} /></header>
      <section className="quran-hero">
        <p className="eyebrow">{ar ? "عالم الحديث" : "Hadith"}</p>
        <h1>{ar ? "كتب الحديث" : "Hadith collections"}</h1>
        <p>{ar ? "النص العربي، وكل حديث مرتبط بمصدره. تظهر الترجمات فقط حيث تأكدت حقوقها." : "Arabic text, every narration linked to its source. Translations appear only where their rights are confirmed."}</p>
        <HadithBrowser locale={locale} />
        <Link className="text-link" href={`/${locale}`}>{ar ? "العودة للرئيسية" : "Return home"}</Link>
      </section>
    </main>
  );
}
