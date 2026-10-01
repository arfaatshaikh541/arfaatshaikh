import { asLocale } from "@/i18n/route-locale";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { HadithBrowser } from "@/components/hadith-browser";
import { LocaleSwitcher } from "@/components/locale-switcher";

export default async function HadithCollectionPage({ params }: { params: Promise<{ locale:string; collection: string }> }) {
  const {locale:rawLocale, collection }=await params;const locale=asLocale(rawLocale);
  const ar = locale === "ar";
  return (
    <main className="quran-landing">
      <header className="topbar"><Brand locale={locale} /><LocaleSwitcher locale={locale} label={ar ? "اللغة" : "Language"} /></header>
      <section className="quran-hero">
        <Link className="text-link" href={`/${locale}/hadith`}>{ar ? "كل المجموعات" : "All collections"}</Link>
        <h1>{ar ? "الكتب" : "Books"}</h1>
        <HadithBrowser locale={locale} collection={collection} />
      </section>
    </main>
  );
}
