import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { getMessages } from "@/i18n/messages";
import { worlds, featureCounts } from "@/lib/worlds";

export default async function WorldsIndex({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
  const ar = locale === "ar";
  const t = getMessages(locale);
  const counts = featureCounts();

  return (
    <main className="worlds-index">
      <header className="topbar">
        <Brand locale={locale} />
        <WorldsNav locale={locale} />
        <LocaleSwitcher locale={locale} label={t.language} />
      </header>
      <section className="worlds-hero">
        <p className="eyebrow">{ar ? "اثنا عشر عالماً" : "Twelve worlds"}</p>
        <h1>{ar ? "عالم الإسلام" : "World of Islam"}</h1>
        <p className="worlds-hero-note">
          {ar
            ? `${counts.available} ميزة متاحة اليوم، والمزيد في الطريق.`
            : `${counts.available} features are live today, with more on the way.`}
        </p>
      </section>
      <section className="world-grid" aria-label={ar ? "العوالم" : "Worlds"}>
        {worlds.map((w) => (
          <Link key={w.slug} href={`/${locale}/w/${w.slug}`} className="world-card">
            <h2>{ar ? w.nameAr : w.name}</h2>
            <p>{ar ? w.taglineAr : w.tagline}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
