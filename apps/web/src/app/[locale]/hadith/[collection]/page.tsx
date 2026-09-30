import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { HadithBrowser } from "@/components/hadith-browser";
import { LocaleSwitcher } from "@/components/locale-switcher";

export default async function HadithCollectionPage({ params }: { params: Promise<{ locale: Locale; collection: string }> }) {
  const { locale, collection } = await params;
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
