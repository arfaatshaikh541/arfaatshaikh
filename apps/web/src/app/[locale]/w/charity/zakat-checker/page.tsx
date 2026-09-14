import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { ZakatFundChecker } from "@/components/zakat-fund-checker";
import { getMessages } from "@/i18n/messages";

export default async function ZakatCheckerPage({ params }: { params: Promise<{ locale: Locale }> }) {
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
        <Link className="text-link" href={`/${locale}/w/charity`}>{ar ? "الصدقة" : "Charity"}</Link>
        <h1>{ar ? "مدقق حوكمة صندوق الزكاة" : "Zakat fund governance checker"}</h1>
        <p>
          {ar
            ? "يستدعي منطق قبول الحوكمة الحقيقي في الخادم (استحقاق ميلستون 16). أدخل إعدادات صندوق افتراضي واعرض نتيجة القبول الحقيقية."
            : "Calls the real, server-side governance acceptance logic (milestone 16). Enter a hypothetical fund's configuration and see the real acceptance result."}
        </p>
      </header>
      <ZakatFundChecker locale={locale} />
    </main>
  );
}
