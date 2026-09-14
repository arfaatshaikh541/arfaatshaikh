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
            ? "حسابات فلكية دقيقة تعمل على جهازك مباشرة، دون إرسال أي بيانات إلى خادم."
            : "Accurate astronomical calculations, computed right on your device — nothing is sent to a server."}
        </p>
      </header>
      <IbadahTools locale={locale} />
    </main>
  );
}
