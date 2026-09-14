import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { featureCounts } from "@/lib/worlds";

export default async function Dashboard({ params }: { params: Promise<{ locale: Locale }> }) {
  const { locale } = await params;
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
        <article><strong>{counts.available}</strong><span>{ar ? "ميزة متاحة الآن" : "Features live now"}</span></article>
        <article><strong>{counts.backendOnly}</strong><span>{ar ? "قيد الإنجاز" : "In progress"}</span></article>
        <article><strong>{counts.planned}</strong><span>{ar ? "قريباً" : "Coming soon"}</span></article>
      </div>
      <p className="hero-actions">
        <Link className="button-link" href={`/${locale}/w`}>{ar ? "استكشف العوالم الاثني عشر" : "Explore the twelve worlds"}</Link>
      </p>
    </div>
  );
}
