import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { IbadahPlanner } from "@/components/ibadah-planner";
import { getMessages } from "@/i18n/messages";

export default async function IbadahPlannerPage({ params }: { params: Promise<{ locale: Locale }> }) {
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
        <Link className="text-link" href={`/${locale}/w/ibadah`}>{ar ? "العبادة" : "Ibadah"}</Link>
        <h1>{ar ? "مخطط العبادة" : "Ibadah planner"}</h1>
        <p>
          {ar ? "رمضان والصيام، وأطوار القمر، ومواعيد الحج والأعياد، ومتابعة الصلاة والحفظ." : "Ramadan and fasting, moon phase, Hajj and Eid dates, and personal prayer and Hifz trackers."}
        </p>
      </header>
      <IbadahPlanner locale={locale} />
    </main>
  );
}
