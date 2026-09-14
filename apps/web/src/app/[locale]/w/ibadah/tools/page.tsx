import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { IbadahTools } from "@/components/ibadah-tools";
import { getMessages } from "@/i18n/messages";

export default async function IbadahToolsPage({ params }: { params: Promise<{ locale: Locale }> }) {
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
        <h1>{ar ? "أدوات العبادة" : "Ibadah tools"}</h1>
        <p>
          {ar
            ? "حسابات فلكية حقيقية تعمل على جهازك مباشرة - لا بيانات وهمية، ولا استدعاء لأي خادم."
            : "Real astronomical calculations, computed on your device - no fabricated data, no server round trip."}
        </p>
      </header>
      <IbadahTools locale={locale} />
    </main>
  );
}
