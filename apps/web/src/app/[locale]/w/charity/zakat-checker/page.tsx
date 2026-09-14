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
        <h1>{ar ? "مدقق صندوق الزكاة" : "Zakat fund checker"}</h1>
        <p>
          {ar
            ? "أدخل إعدادات صندوق افتراضي واعرض نتيجة القبول."
            : "Enter a hypothetical fund's configuration and see whether it meets the acceptance rules."}
        </p>
      </header>
      <ZakatFundChecker locale={locale} />
    </main>
  );
}
