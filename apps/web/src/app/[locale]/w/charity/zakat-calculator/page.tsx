import type { Locale } from "@world-of-islam/shared-types";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { WorldsNav } from "@/components/worlds-nav";
import { ZakatCalculator } from "@/components/zakat-calculator";
import { getMessages } from "@/i18n/messages";

export default async function ZakatCalculatorPage({ params }: { params: Promise<{ locale: Locale }> }) {
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
        <h1>{ar ? "حاسبة الزكاة" : "Zakat calculator"}</h1>
        <p>
          {ar ? "قدّر الزكاة المستحقة على مالك. يتم الحساب على جهازك." : "Estimate the zakat due on your wealth. Everything is calculated on your device."}
        </p>
      </header>
      <ZakatCalculator locale={locale} />
    </main>
  );
}
