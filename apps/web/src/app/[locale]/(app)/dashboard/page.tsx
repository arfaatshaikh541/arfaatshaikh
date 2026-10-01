import { asLocale } from "@/i18n/route-locale";
import Link from "next/link";
import { featureCounts } from "@/lib/worlds";

export default async function Dashboard({ params }: { params: Promise<{ locale:string }> }) {
  const {locale:rawLocale }=await params;const locale=asLocale(rawLocale);
  const ar = locale === "ar";
  const counts = featureCounts();
  return (
    <div>
      <p className="eyebrow">{ar ? "لوحة عالم الإسلام" : "World of Islam dashboard"}</p>
      <h1 className="page-title">{ar ? "أهلاً بعودتك" : "Welcome back"}</h1>
      <p>
        {ar
          ? "تصفّح العوالم الاثني عشر لعالم الإسلام أدناه."
          : "Browse the twelve worlds of the platform below."}
      </p>
      <div className="metric-grid">
        <article><strong>{counts.byStatus.IMPLEMENTED}</strong><span>{ar ? "قدرة منجزة" : "Capabilities implemented"}</span></article>
        <article><strong>{counts.byStatus.PARTIALLY_IMPLEMENTED + counts.byStatus.NOT_VERIFIED}</strong><span>{ar ? "جزئياً أو غير موثّق" : "Partly built or not yet verified"}</span></article>
        <article><strong>{counts.byStatus.DATA_SOURCE_REQUIRED + counts.byStatus.ARCHITECTURE_READY}</strong><span>{ar ? "جاهز وينتظر البيانات" : "Built, waiting for data"}</span></article>
      </div>
      <p className="hero-actions">
        <Link className="button-link" href={`/${locale}/w`}>{ar ? "استكشف العوالم الاثني عشر" : "Explore the twelve worlds"}</Link>
      </p>
    </div>
  );
}
