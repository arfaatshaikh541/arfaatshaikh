import { asLocale } from "@/i18n/route-locale";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { getMessages } from "@/i18n/messages";
import { worlds, featureCounts } from "@/lib/worlds";

export default async function WorldsIndex({ params }: { params: Promise<{ locale:string }> }) {
  const {locale:rawLocale }=await params;const locale=asLocale(rawLocale);
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
            ? `${counts.byStatus.IMPLEMENTED} قدرة منجزة و${counts.byStatus.PARTIALLY_IMPLEMENTED} منجزة جزئياً من ${counts.total}. الباقي ينتظر مصادر بيانات موثقة.`
            : `${counts.byStatus.IMPLEMENTED} of ${counts.total} capabilities are implemented and ${counts.byStatus.PARTIALLY_IMPLEMENTED} partly; the rest wait for verified data sources.`}
        </p>
        <p className="worlds-hero-note"><Link className="text-link" href={`/${locale}/status`}>{ar ? "حالة كل قدرة وكل مصدر" : "The status of every capability and every source"}</Link></p>
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
