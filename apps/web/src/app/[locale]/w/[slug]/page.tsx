import { asLocale } from "@/i18n/route-locale";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { getMessages } from "@/i18n/messages";
import { findWorld, worlds, type FeatureStatus } from "@/lib/worlds";

export function generateStaticParams() {
  return worlds.map((w) => ({ slug: w.slug }));
}

const STATUS_LABEL: Record<FeatureStatus, { en: string; ar: string }> = {
  IMPLEMENTED: { en: "Implemented", ar: "مُنجز" },
  PARTIALLY_IMPLEMENTED: { en: "Partly implemented", ar: "منجز جزئياً" },
  NOT_VERIFIED: { en: "Not yet verified", ar: "لم يُتحقق منه بعد" },
  DATA_SOURCE_REQUIRED: { en: "Data source required", ar: "يتطلب مصدر بيانات" },
  ARCHITECTURE_READY: { en: "Ready for data", ar: "جاهز لاستقبال البيانات" },
  NOT_IMPLEMENTED: { en: "Not built", ar: "غير مبني" },
};

export default async function WorldPage({ params }: { params: Promise<{ locale:string; slug: string }> }) {
  const {locale:rawLocale, slug }=await params;const locale=asLocale(rawLocale);
  const world = findWorld(slug);
  if (!world) notFound();
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
        <Link className="text-link" href={`/${locale}/w`}>{ar ? "كل العوالم" : "All worlds"}</Link>
        <h1>{ar ? world.nameAr : world.name}</h1>
        <p>{ar ? world.taglineAr : world.tagline}</p>
      </header>
      <ul className="feature-list" aria-label={ar ? "القدرات" : "Capabilities"}>
        {world.features.map((feat) => {
          const label = STATUS_LABEL[feat.status];
          const body = (
            <>
              <div className="feature-list-head">
                <h2>{feat.name}</h2>
                <span className={`status-pill status-${feat.status.toLowerCase().replaceAll("_", "-")}`}>{ar ? label.ar : label.en}</span>
              </div>
              <p>{feat.note}</p>
            </>
          );
          return (
            <li key={feat.id} className={feat.status === "IMPLEMENTED" || feat.status === "PARTIALLY_IMPLEMENTED" ? "feature-item feature-item-live" : "feature-item"}>
              {feat.href && feat.status !== "NOT_IMPLEMENTED" ? (
                <Link href={`/${locale}${feat.href}`} className="feature-item-link">{body}</Link>
              ) : (
                body
              )}
            </li>
          );
        })}
      </ul>
    </main>
  );
}
